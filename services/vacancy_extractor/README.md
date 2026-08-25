# Vacancy Extractor

Local deterministic service that converts a job-posting URL or HTML document
into the Adapt My CV vacancy schema. It does not use an AI model.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn vacancy_extractor.api:app --host 127.0.0.1 --port 8010
```

The simple vacancy dashboard is available at `http://127.0.0.1:8010/`.
OpenAPI documentation remains available at `http://127.0.0.1:8010/docs`.

## n8n request

Use an HTTP Request node:

- Method: `POST`
- URL: `http://host.docker.internal:8010/extract` when n8n runs in Docker
- Body type: JSON
- Body: `{"url": "{{$json.url}}"}`

For already downloaded HTML, send `{"html": "...", "source_url": "..."}`.
