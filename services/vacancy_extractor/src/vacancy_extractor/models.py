from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class ExtractRequest(BaseModel):
    url: HttpUrl | None = None
    html: str | None = Field(default=None, max_length=3_000_000)
    source_url: HttpUrl | None = None

    @model_validator(mode="after")
    def require_one_source(self) -> "ExtractRequest":
        if bool(self.url) == bool(self.html):
            raise ValueError("Provide exactly one of 'url' or 'html'.")
        return self


class SourceInfo(BaseModel):
    url: str | None = None
    platform: str | None = None
    extracted_at: str


class JobData(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    work_model: str = ""
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    salary: str | None = None


class ExtractionInfo(BaseModel):
    method: Literal["json_ld", "html_heuristic"]
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VacancyDocument(BaseModel):
    source: SourceInfo
    job: JobData
    extraction: ExtractionInfo
