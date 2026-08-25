from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException

from .extractor import extract_vacancy
from .models import ExtractRequest, VacancyDocument
from .safety import UnsafeUrlError, validate_public_url

app = FastAPI(title="Adapt My CV Vacancy Extractor", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def fetch_html(url: str) -> tuple[str, str]:
    validate_public_url(url)
    headers = {"User-Agent": "AdaptMyCV/0.1 (+local vacancy extraction)"}
    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=False) as client:
        current = url
        for _ in range(4):
            response = await client.get(current)
            if response.is_redirect:
                destination = str(response.next_request.url)
                validate_public_url(destination)
                current = destination
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise HTTPException(status_code=422, detail="The URL did not return HTML.")
            if len(response.content) > 3_000_000:
                raise HTTPException(status_code=413, detail="The HTML response exceeds 3 MB.")
            return response.text, str(response.url)
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
