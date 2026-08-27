from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from .extractor import extract_vacancy
from .models import ExtractRequest, VacancyDocument
from .platforms import api_payload_to_html, plan_fetch
from .safety import UnsafeUrlError, validate_public_url

app = FastAPI(title="Adapt My CV Vacancy Extractor", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
UI_PATH = Path(__file__).with_name("static") / "index.html"


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def fetch_html(url: str) -> tuple[str, str]:
    original_url = url
    plan = plan_fetch(url)
    validate_public_url(plan.fetch_url)
    headers = {"User-Agent": "AdaptMyCV/0.1 (+local vacancy extraction)"}
    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=False) as client:
        current = plan.fetch_url
        for _ in range(4):
            response = await client.get(current)
            if response.is_redirect:
                destination = str(response.next_request.url)
                validate_public_url(destination)
                current = destination
                continue
            response.raise_for_status()
            if len(response.content) > 3_000_000:
                raise HTTPException(status_code=413, detail="The vacancy response exceeds 3 MB.")
            if plan.kind != "html":
                try:
                    return api_payload_to_html(plan, response.json()), original_url
                except (ValueError, TypeError) as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise HTTPException(status_code=422, detail="The URL did not return HTML.")
            return response.text, original_url
    raise HTTPException(status_code=422, detail="Too many redirects.")


@app.post("/extract", response_model=VacancyDocument)
async def extract(request: ExtractRequest) -> VacancyDocument:
    try:
        if request.url:
            html, source_url = await fetch_html(str(request.url))
        else:
            html, source_url = request.html or "", str(request.source_url) if request.source_url else None
        return extract_vacancy(html, source_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Job page returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="The job page could not be fetched.") from exc
