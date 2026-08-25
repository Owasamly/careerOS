from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .models import ExtractionInfo, JobData, SourceInfo, VacancyDocument


SECTION_NAMES = {
    "responsibilities": ("responsibilities", "what you will do", "your tasks", "the role", "duties"),
    "requirements": ("requirements", "what you bring", "your profile", "qualifications", "must have"),
    "nice_to_haves": ("nice to have", "preferred", "bonus", "desirable", "ideally"),
}

SKILL_TERMS = (
    "aws", "azure", "gcp", "python", "java", "javascript", "typescript", "linux", "docker",
    "kubernetes", "terraform", "ansible", "git", "sql", "siem", "iam", "cloudtrail",
    "guardduty", "security hub", "incident response", "vulnerability management", "splunk",
)

LANGUAGE_TERMS = {
    "english": "English", "german": "German", "deutsch": "German", "french": "French",
    "spanish": "Spanish", "italian": "Italian", "dutch": "Dutch", "polish": "Polish",
    "arabic": "Arabic", "tigrinya": "Tigrinya",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(filter(None, (clean_text(item) for item in value)))
    text = BeautifulSoup(unescape(str(value)), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    text = clean_text(value)
    if not text:
        return []
    parts = re.split(r"(?:\s*[•·]\s*|\n+|;\s+)", text)
    return [part.strip(" -") for part in parts if part.strip(" -")]


def find_jobposting(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        for item in value:
            found = find_jobposting(item)
            if found:
                return found
    elif isinstance(value, dict):
        kind = value.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            return value
        for key in ("@graph", "mainEntity", "itemListElement"):
            found = find_jobposting(value.get(key))
            if found:
                return found
    return None


def location_from_json_ld(value: Any) -> str:
    locations = value if isinstance(value, list) else [value]
    results: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address", location)
        if isinstance(address, dict):
            results.append(", ".join(filter(None, [clean_text(address.get("addressLocality")), clean_text(address.get("addressRegion")), clean_text(address.get("addressCountry"))])))
        else:
            results.append(clean_text(address))
    return " / ".join(filter(None, results))


def organization_name(value: Any) -> str:
    if isinstance(value, dict):
        return clean_text(value.get("name"))
    return clean_text(value)


def salary_from_json_ld(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    currency = clean_text(value.get("currency"))
    amount = value.get("value", value)
    if isinstance(amount, dict):
        minimum, maximum = amount.get("minValue"), amount.get("maxValue")
        unit = clean_text(amount.get("unitText"))
        numeric = f"{minimum}-{maximum}" if minimum is not None and maximum is not None else clean_text(amount.get("value"))
        return " ".join(filter(None, [currency, numeric, unit])) or None
    return " ".join(filter(None, [currency, clean_text(amount)])) or None


def extract_sections(soup: BeautifulSoup) -> dict[str, list[str]]:
    sections = {key: [] for key in SECTION_NAMES}
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading_text = clean_text(heading.get_text(" ", strip=True)).lower()
        target = next((key for key, names in SECTION_NAMES.items() if any(name in heading_text for name in names)), None)
        if not target:
            continue
        items: list[str] = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and re.match(r"^h[1-6]$", sibling.name or ""):
                break
            if isinstance(sibling, Tag):
                list_items = sibling.find_all("li")
                if list_items:
                    items.extend(clean_text(item.get_text(" ", strip=True)) for item in list_items)
                elif sibling.name == "p":
                    paragraph = clean_text(sibling.get_text(" ", strip=True))
                    if paragraph:
                        items.append(paragraph)
        sections[target].extend(item for item in items if item)
    return {key: list(dict.fromkeys(values)) for key, values in sections.items()}


def derive_skills(job: JobData) -> list[str]:
    searchable = " ".join([job.description, *job.responsibilities, *job.requirements, *job.nice_to_haves]).lower()
    return [term.upper() if term in {"aws", "gcp", "iam", "sql", "siem"} else term.title() for term in SKILL_TERMS if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", searchable)]


def derive_languages(job: JobData) -> list[str]:
    searchable = " ".join([job.description, *job.requirements, *job.nice_to_haves]).lower()
    return list(dict.fromkeys(label for term, label in LANGUAGE_TERMS.items() if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", searchable)))


def extract_vacancy(html: str, source_url: str | None = None) -> VacancyDocument:
    soup = BeautifulSoup(html, "html.parser")
    structured: dict[str, Any] | None = None
    warnings: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        try:
            structured = find_jobposting(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            warnings.append("A JSON-LD block was present but invalid.")
        if structured:
            break

    sections = extract_sections(soup)
    if structured:
        description = clean_text(structured.get("description"))
        job = JobData(
            title=clean_text(structured.get("title")),
            company=organization_name(structured.get("hiringOrganization")),
            location=location_from_json_ld(structured.get("jobLocation")),
            employment_type=clean_text(structured.get("employmentType")),
            work_model="Remote" if structured.get("jobLocationType") == "TELECOMMUTE" else "",
            description=description,
            responsibilities=listify(structured.get("responsibilities")) or sections["responsibilities"],
            requirements=listify(structured.get("qualifications") or structured.get("experienceRequirements")) or sections["requirements"],
            nice_to_haves=listify(structured.get("skills")) or sections["nice_to_haves"],
            salary=salary_from_json_ld(structured.get("baseSalary")),
        )
        method = "json_ld"
    else:
        title_node = soup.find("h1") or soup.find("title")
        company_node = soup.select_one("[class*='company' i], [data-company]")
        location_node = soup.select_one("[class*='location' i], [data-location]")
        main = soup.find("main") or soup.find("article") or soup.body
        job = JobData(
            title=clean_text(title_node.get_text(" ", strip=True) if title_node else ""),
            company=clean_text(company_node.get_text(" ", strip=True) if company_node else ""),
            location=clean_text(location_node.get_text(" ", strip=True) if location_node else ""),
            description=clean_text(main.get_text(" ", strip=True) if main else ""),
            responsibilities=sections["responsibilities"],
            requirements=sections["requirements"],
            nice_to_haves=sections["nice_to_haves"],
        )
        method = "html_heuristic"
        warnings.append("No JobPosting JSON-LD was found; visible-page heuristics were used.")

    job.skills = derive_skills(job)
    job.languages = derive_languages(job)
    required = ("title", "company", "description", "requirements")
    missing = [field for field in required if not getattr(job, field)]
    completeness = (len(required) - len(missing)) / len(required)
    confidence = round((0.72 if method == "json_ld" else 0.42) + completeness * (0.25 if method == "json_ld" else 0.35), 2)
    hostname = urlparse(source_url).hostname if source_url else None
    return VacancyDocument(
        source=SourceInfo(url=source_url, platform=hostname, extracted_at=datetime.now(timezone.utc).isoformat()),
        job=job,
        extraction=ExtractionInfo(method=method, confidence=min(confidence, 0.99), missing_fields=missing, warnings=warnings),
    )
