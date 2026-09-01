from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .models import ContactPerson, ExtractionInfo, JobData, LanguageRequirement, SourceInfo, VacancyDocument


SECTION_NAMES = {
    "responsibilities": (
        "responsibilities", "what you will do", "what you'll do", "what you’ll do", "what you'll be doing", "what you’ll be doing", "the work you'll do", "the work you’ll do", "more specifically, you will", "your role in our space mission", "your tasks", "tasks", "your mission", "the role", "duties",
        "deine aufgaben", "ihre aufgaben", "aufgabenbereich", "das erwartet dich",
        "das erwartet sie", "was dich erwartet", "deine mission", "ihre mission", "tätigkeiten", "verantwortlichkeiten",
    ),
    "requirements": (
        "requirements", "what you bring", "your profile", "qualifications", "qualification checklist", "the qualifications you need", "qualities you'll need", "qualities you’ll need", "you're a fit if", "you’re a fit if", "must have",
        "dein profil", "ihr profil", "das bringst du mit", "das bringen sie mit",
        "was du mitbringst", "anforderungen", "qualifikationen", "voraussetzungen",
    ),
    "nice_to_haves": (
        "nice to have", "preferred", "bonus", "desirable", "ideally",
        "wünschenswert", "von vorteil", "idealerweise", "zusätzliche qualifikationen",
    ),
}

SKILL_TERMS = (
    "aws", "azure", "gcp", "python", "java", "javascript", "typescript", "linux", "docker",
    "kubernetes", "terraform", "ansible", "git", "sql", "siem", "iam", "cloudtrail",
    "guardduty", "security hub", "incident response", "vulnerability management", "splunk",
    "ai", "artificial intelligence", "microsoft 365", "power automate", "power bi", "n8n",
    "zapier", "make", "notion", "salesforce", "excel",
)

LANGUAGE_TERMS = {
    "english": "English", "englisch": "English", "englischkenntnisse": "English",
    "german": "German", "deutsch": "German", "deutschkenntnisse": "German",
    "french": "French", "französisch": "French", "spanish": "Spanish", "spanisch": "Spanish",
    "italian": "Italian", "italienisch": "Italian", "dutch": "Dutch", "niederländisch": "Dutch",
    "polish": "Polish", "polnisch": "Polish", "arabic": "Arabic", "arabisch": "Arabic",
    "tigrinya": "Tigrinya",
}

LEVEL_PATTERNS = (
    (r"\b(c2|c1|b2|b1|a2|a1)\b", lambda match: match.group(1).upper()),
    (r"\b(native|mother tongue|muttersprach\w*)\b", lambda _: "Native"),
    (r"\b(fluent|fluency|fließend\w*|fliessend\w*|flüssig\w*|verhandlungssicher\w*)\b", lambda _: "Fluent"),
    (r"\b(professional|business fluent|geschäftssicher\w*|gute\w* kenntnisse|very good)\b", lambda _: "Professional"),
    (r"\b(basic|grundkenntnisse)\b", lambda _: "Basic"),
)

CONTACT_HEADINGS = (
    "contact", "contact person", "questions", "your contact", "recruiter",
    "kontakt", "ansprechpartner", "ansprechpartnerin", "fragen", "dein kontakt", "ihr kontakt",
)


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
    headings = [*soup.find_all(re.compile(r"^h[1-6]$")), *soup.select(".headline")]
    for heading in headings:
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
    found: list[str] = []
    for term in SKILL_TERMS:
        if term == "make":
            matched = bool(re.search(r"\bmake\.com\b|\bmake\s+(?:automation|workflow|integration)s?\b", searchable))
        else:
            matched = bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", searchable))
        if matched:
            found.append(term.upper() if term in {"aws", "gcp", "iam", "sql", "siem", "ai"} else term.title())
    return found


def derive_languages(job: JobData, soup: BeautifulSoup) -> list[LanguageRequirement]:
    evidence_lines = [*job.requirements, *job.nice_to_haves]
    if not evidence_lines:
        evidence_lines = []
        for node in soup.select("li, p, label, [class*='requirement' i], [class*='qualification' i]"):
            value = clean_text(node.get_text(" ", strip=True))
            lowered = value.lower()
            if 4 <= len(value) <= 350 and any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered) for term in LANGUAGE_TERMS):
                evidence_lines.append(value)
        evidence_lines = list(dict.fromkeys(evidence_lines))
    found: dict[str, LanguageRequirement] = {}
    for evidence in evidence_lines:
        lowered = evidence.lower()
        for term, language in LANGUAGE_TERMS.items():
            if not re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered):
                continue
            clauses = [part.strip() for part in re.split(r"(?<=[.!?;])\s+|\s+[–—]\s+|\s+(?:and|und|sowie)\s+", lowered) if part.strip()]
            local = next((part for part in clauses if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", part)), lowered)
            level = "Not specified"
            cefr_levels = set(re.findall(r"\b(?:c2|c1|b2|b1|a2|a1)\b", local, re.I))
            if len(cefr_levels) == 1:
                level = next(iter(cefr_levels)).upper()
            elif not cefr_levels:
                for pattern, formatter in LEVEL_PATTERNS[1:]:
                    match = re.search(pattern, local, re.I)
                    if match:
                        level = formatter(match)
                        break
            explicitly_optional = bool(re.search(r"\b(?:isn't|is not|not) required\b|\boptional\b|\bnice to have\b|\bhelps?\b|\bvon vorteil\b|\bwünschenswert\b", local))
            required = not explicitly_optional and (evidence in job.requirements or bool(re.search(r"\b(required|must|erforderlich|vorausgesetzt|zwingend)\b", local)))
            candidate = LanguageRequirement(language=language, level=level, evidence=evidence, required=required)
            current = found.get(language)
            if not current or (current.level == "Not specified" and level != "Not specified") or (required and not current.required):
                found[language] = candidate
    return list(found.values())


def extract_contact(soup: BeautifulSoup) -> ContactPerson | None:
    scope: Tag | None = None
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading_text = clean_text(heading.get_text(" ", strip=True)).lower()
        if any(label in heading_text for label in CONTACT_HEADINGS):
            scope = heading.parent if isinstance(heading.parent, Tag) else heading
            break
    if scope is None:
        scope = soup.select_one("[class*='contact' i], [class*='recruit' i], [data-testid*='contact' i]")

    search_root: Tag | BeautifulSoup = scope or soup
    email_link = search_root.select_one("a[href^='mailto:']")
    phone_link = search_root.select_one("a[href^='tel:']")
    if not scope and not email_link and not phone_link:
        return None
    email = clean_text(email_link.get("href", "").removeprefix("mailto:").split("?", 1)[0]) if email_link else ""
    phone = clean_text(phone_link.get("href", "").removeprefix("tel:")) if phone_link else ""

    name = ""
    role = ""
    if scope:
        candidates = [clean_text(node.get_text(" ", strip=True)) for node in scope.select("h3, h4, strong, [class*='name' i], p")]
        candidates = [value for value in candidates if value and value not in {email, phone} and not any(label == value.lower() for label in CONTACT_HEADINGS)]
        name_pattern = re.compile(r"^[A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+(?:\s+[A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+){1,3}$")
        name = next((value for value in candidates if name_pattern.match(value)), "")
        role = next((value for value in candidates if value != name and any(word in value.lower() for word in ("recruit", "talent", "people", "personal", "human resources", "hr"))), "")
    if not any((name, role, email, phone)):
        return None
    return ContactPerson(name=name, role=role, email=email, phone=phone)


def company_from_page(soup: BeautifulSoup, source_url: str | None) -> str:
    company_node = soup.select_one("[class*='company' i], [data-company]")
    if company_node:
        value = clean_text(company_node.get_text(" ", strip=True))
        if value:
            return value
    site_name = soup.select_one("meta[property='og:site_name'], meta[name='application-name']")
    if site_name and site_name.get("content"):
        return clean_text(site_name.get("content"))
    hostname = urlparse(source_url).hostname if source_url else ""
    if hostname and ".jobs.personio." in hostname:
        tenant = hostname.split(".jobs.personio.", 1)[0].split(".")[-1]
        return tenant.replace("-", " ").title()
    return ""


def page_blockers(soup: BeautifulSoup, job: JobData) -> list[str]:
    title = clean_text((soup.title.string if soup.title else "") or "").lower()
    headings = " ".join(clean_text(node.get_text(" ", strip=True)).lower() for node in soup.find_all(re.compile(r"^h[1-3]$")))
    blockers: list[str] = []
    challenge_markers = ("access denied", "just a moment", "verify you are human", "captcha", "bot detection")
    login_markers = ("sign in", "log in", "anmelden", "login")
    if any(marker in title or marker in headings for marker in challenge_markers):
        blockers.append("The supplied page appears to be an access challenge or bot-protection page.")
    elif any(marker == title or marker in headings for marker in login_markers) and len(job.description) < 1200:
        blockers.append("The supplied page appears to require authentication rather than showing a public vacancy.")

    form_fields = len(soup.select("input, textarea, select"))
    if form_fields >= 5 and not job.responsibilities and not job.requirements:
        blockers.append("The supplied page appears to be an application form, not the job description.")
    if not job.title:
        blockers.append("A job title is required before CV generation.")
    evidence_count = len(job.responsibilities) + len(job.requirements)
    if len(job.description) < 120 and evidence_count < 2:
        blockers.append("The extracted job description is too short to tailor a CV safely.")
    if not job.responsibilities and not job.requirements:
        blockers.append("Neither responsibilities nor requirements could be identified.")
    return list(dict.fromkeys(blockers))


def field_confidence(job: JobData, method: str) -> dict[str, float]:
    base = 0.92 if method == "json_ld" else 0.72
    return {
        "title": base if job.title else 0.0,
        "company": base if job.company else 0.0,
        "description": base if len(job.description) >= 120 else (0.35 if job.description else 0.0),
        "responsibilities": base if len(job.responsibilities) >= 2 else (0.48 if job.responsibilities else 0.0),
        "requirements": base if len(job.requirements) >= 2 else (0.48 if job.requirements else 0.0),
        "skills": 0.7 if job.skills else 0.0,
        "languages": 0.85 if job.languages else 0.0,
        "contact": 0.85 if job.contact else 0.0,
    }


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
        raw_description = unescape(str(structured.get("description") or ""))
        description_soup = BeautifulSoup(raw_description, "html.parser")
        description_sections = extract_sections(description_soup)
        for section_name in sections:
            if not sections[section_name]:
                sections[section_name] = description_sections[section_name]
        description = clean_text(raw_description)
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
        location_node = soup.select_one("[class*='location' i], [data-location]")
        main = soup.find("main") or soup.find("article") or soup.body
        job = JobData(
            title=clean_text(title_node.get_text(" ", strip=True) if title_node else ""),
            company=company_from_page(soup, source_url),
            location=clean_text(location_node.get_text(" ", strip=True) if location_node else ""),
            description=clean_text(main.get_text(" ", strip=True) if main else ""),
            responsibilities=sections["responsibilities"],
            requirements=sections["requirements"],
            nice_to_haves=sections["nice_to_haves"],
        )
        method = "html_heuristic"
        warnings.append("No JobPosting JSON-LD was found; visible-page heuristics were used.")

    job.skills = derive_skills(job)
    job.languages = derive_languages(job, soup)
    job.contact = extract_contact(soup)
    required = ("title", "company", "description", "requirements", "responsibilities")
    missing = [field for field in required if not getattr(job, field)]
    completeness = (len(required) - len(missing)) / len(required)
    confidence = round((0.72 if method == "json_ld" else 0.42) + completeness * (0.25 if method == "json_ld" else 0.35), 2)
    blockers = page_blockers(soup, job)
    sparse_sections = [name for name in ("responsibilities", "requirements") if len(getattr(job, name)) == 1]
    if sparse_sections:
        warnings.append(f"Only one item was found for: {', '.join(sparse_sections)}.")
    if not job.skills:
        warnings.append("No technical skills were detected from vacancy evidence.")
    if blockers:
        status = "failed"
    elif missing or confidence < 0.75:
        status = "needs_review"
    else:
        status = "ready"
    hostname = urlparse(source_url).hostname if source_url else None
    return VacancyDocument(
        source=SourceInfo(url=source_url, platform=hostname, extracted_at=datetime.now(timezone.utc).isoformat()),
        job=job,
        extraction=ExtractionInfo(
            method=method,
            status=status,
            can_generate_cv=not blockers,
            confidence=min(confidence, 0.99),
            missing_fields=missing,
            blockers=blockers,
            field_confidence=field_confidence(job, method),
            warnings=warnings,
        ),
    )
