# Adapt My CV

Local-first CV mapping and PDF generation. The application does not call an AI
model or send candidate/vacancy JSON to an external API. PDF files are rendered
inside the browser with `@react-pdf/renderer`.

Adapt My CV is a vacancy-to-resume workspace. The first product slice defines
the data contract through a static interface before any tailoring or rendering
API is connected.

## Current interface

- Paste or upload a canonical candidate-profile JSON file.
- Paste or upload a structured job-vacancy JSON file.
- Validate JSON locally in the browser.
- Choose rewriting strength and target length.
- Define which resume sections may be rewritten, ranked, selected, or preserved.
- Review the tailoring brief before any data is sent.
- Use Reactive Resume as the intended PDF renderer.

## Planned phases

1. Formal JSON schemas and detailed field-level validation.
2. Evidence-backed tailoring service.
3. Reactive Resume import, patch, and PDF endpoints.
4. PDF content and visual verification.
5. Optional n8n orchestration.

## Local services

- `services/vacancy_extractor`: deterministic job URL/HTML extraction API for
  n8n. It prefers Schema.org `JobPosting` JSON-LD and falls back to visible HTML.

## Local development

```bash
pnpm install
pnpm dev
```
