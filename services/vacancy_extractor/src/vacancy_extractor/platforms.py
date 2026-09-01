from __future__ import annotations

from dataclasses import dataclass
from html import escape, unescape
import re
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class FetchPlan:
    platform: str
    fetch_url: str
    kind: str = "html"
    job_id: str = ""
    account: str = ""


def plan_fetch(url: str) -> FetchPlan:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]

    if ".jobs.personio." in host:
        # Personio's /apply page contains the form, not the vacancy description.
        path = re.sub(r"(/job/[^/]+)/apply/?$", r"\1", parsed.path, flags=re.I)
        account = host.split(".jobs.personio.", 1)[0]
        job_match = re.search(r"/job/(\d+)", path, re.I)
        if account == "crozdach" and job_match:
            language = (parse_qs(parsed.query).get("language") or ["de"])[0]
            return FetchPlan("personio", f"{parsed.scheme}://{host}/xml?language={language}", "personio_xml", job_match.group(1), account)
        return FetchPlan("personio", urlunparse(parsed._replace(path=path)), account=account)

    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(parts) >= 2:
        region = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        return FetchPlan("lever", f"https://{region}/v0/postings/{parts[0]}/{parts[1]}", "lever_json", parts[1], parts[0])

    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        job_id = parts[1] if parts[1] != "apply" else (parts[2] if len(parts) > 2 else "")
        return FetchPlan("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}", "ashby_json", job_id, parts[0])

    if host == "careers.celonis.com" and parsed.path.rstrip("/").endswith("/job-detail"):
        job_id = (parse_qs(parsed.query).get("jobId") or [""])[0]
        if job_id.isdigit():
            return FetchPlan("celonis", f"https://dxp-api.celonis.com/v1/jobs/{job_id}", "celonis_json", job_id, "Celonis")

    greenhouse_hosts = {"boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"}
    if host in greenhouse_hosts and "jobs" in parts:
        index = parts.index("jobs")
        if index > 0 and len(parts) > index + 1:
            board, job_id = parts[index - 1], parts[index + 1]
            return FetchPlan("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?content=true", "greenhouse_json", job_id, board)

    return FetchPlan(host or "unknown", url)


def _section(title: str, content: str) -> str:
    return f"<h2>{escape(title)}</h2>{content}" if content else ""


def normalize_rich_sections(content: str) -> str:
    soup = BeautifulSoup(unescape(content), "html.parser")
    for paragraph in soup.find_all("p"):
        strong = paragraph.find("strong", recursive=False)
        if not strong:
            continue
        paragraph_text = " ".join(paragraph.get_text(" ", strip=True).split())
        strong_text = " ".join(strong.get_text(" ", strip=True).split())
        if paragraph_text.rstrip(":") != strong_text.rstrip(":"):
            continue
        heading = soup.new_tag("h2")
        heading.string = strong_text.rstrip(":")
        paragraph.replace_with(heading)
    return str(soup)


def lever_to_html(data: dict[str, Any], account: str) -> str:
    categories = data.get("categories") or {}
    lists = "".join(_section(str(item.get("text", "")), str(item.get("content", ""))) for item in data.get("lists", []))
    return (
        "<html><head>"
        f'<meta name="application-name" content="{escape(account.replace("-", " ").title())}">'
        "</head><body><main>"
        f"<h1>{escape(str(data.get('text', '')))}</h1>"
        f'<div class="job-location">{escape(str(categories.get("location", "")))}</div>'
        f"{data.get('description', '')}{lists}{data.get('additional', '')}"
        "</main></body></html>"
    )


def ashby_to_html(data: dict[str, Any], account: str, job_id: str) -> str:
    jobs = data.get("jobs") or []
    job = next((item for item in jobs if job_id and job_id in f"{item.get('jobUrl', '')} {item.get('applyUrl', '')}"), None)
    if job is None:
        raise ValueError("The Ashby vacancy was not found on that public job board.")
    location = job.get("location", "")
    secondary = [item.get("location", "") for item in job.get("secondaryLocations") or []]
    locations = " / ".join(filter(None, [location, *secondary]))
    return (
        "<html><head>"
        f'<meta name="application-name" content="{escape(account.replace("-", " ").title())}">'
        "</head><body><main>"
        f"<h1>{escape(str(job.get('title', '')))}</h1>"
        f'<div class="job-location">{escape(locations)}</div>'
        f"{normalize_rich_sections(str(job.get('descriptionHtml', '')))}"
        "</main></body></html>"
    )


def celonis_to_html(data: dict[str, Any]) -> str:
    return (
        "<html><head><meta name=\"application-name\" content=\"Celonis\"></head><body><main>"
        f"<h1>{escape(str(data.get('title', '')))}</h1>"
        f'<div class="job-location">{escape(str(data.get("groupedLocation", "")))}</div>'
        f"{normalize_rich_sections(str(data.get('description', '')))}"
        "</main></body></html>"
    )


def personio_xml_to_html(content: str, plan: FetchPlan) -> str:
    root = ElementTree.fromstring(content)
    position = next((item for item in root.findall("position") if (item.findtext("id") or "") == plan.job_id), None)
    if position is None:
        raise ValueError("The vacancy was not found in the public Personio XML feed.")
    descriptions = position.findall("./jobDescriptions/jobDescription")
    rich_description = "".join((item.findtext("value") or "") for item in descriptions)
    soup = BeautifulSoup(rich_description, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    lines = [" ".join(line.split()) for line in soup.get_text(" ", strip=False).splitlines() if line.strip()]

    def answer_after(pattern: str) -> str:
        for index, line in enumerate(lines[:-1]):
            if re.search(pattern, line, re.I):
                return lines[index + 1]
        return ""

    responsibilities = answer_after(r"(?:welchen|welche|bei welchen).*aufgaben|aufgaben.*(?:hilfe|unterstützung)")
    requirements = answer_after(r"fähigkeiten|sprachkenntnisse|vorkenntnisse|voraussetzungen|anforderungen")
    known_companies = {"crozdach": "CROZ DACH GmbH"}
    company = position.findtext("subcompany") or known_companies.get(plan.account) or plan.account.replace("-", " ").title()
    offices = [position.findtext("office") or "", *[item.text or "" for item in position.findall("./additionalOffices/office")]]
    return (
        "<html><head><meta charset=\"utf-8\">"
        f'<meta name="application-name" content="{escape(company)}">'
        "</head><body><main>"
        f"<h1>{escape(position.findtext('name') or '')}</h1>"
        f'<div class="job-location">{escape(" / ".join(filter(None, offices)))}</div>'
        f"<div>{rich_description}</div>"
        f"{_section('Responsibilities', f'<p>{escape(responsibilities)}</p>' if responsibilities else '')}"
        f"{_section('Requirements', f'<p>{escape(requirements)}</p>' if requirements else '')}"
        "</main></body></html>"
    )


def greenhouse_to_html(data: dict[str, Any], account: str) -> str:
    location = (data.get("location") or {}).get("name", "")
    company = str(data.get("company_name") or account.replace("-", " ").title())
    return (
        "<html><head>"
        f'<meta name="application-name" content="{escape(company)}">'
        "</head><body><main>"
        f"<h1>{escape(str(data.get('title', '')))}</h1>"
        f'<div class="job-location">{escape(str(location))}</div>'
        f"{normalize_rich_sections(str(data.get('content', '')))}"
        "</main></body></html>"
    )


def api_payload_to_html(plan: FetchPlan, data: dict[str, Any]) -> str:
    if plan.kind == "lever_json":
        return lever_to_html(data, plan.account)
    if plan.kind == "ashby_json":
        return ashby_to_html(data, plan.account, plan.job_id)
    if plan.kind == "greenhouse_json":
        return greenhouse_to_html(data, plan.account)
    if plan.kind == "celonis_json":
        return celonis_to_html(data)
    raise ValueError(f"Unsupported ATS payload type: {plan.kind}")
