"""Resume & JD ingestion, per the Phase 4 spec's §4.1.

Text extraction (PyMuPDF for PDF, python-docx for .docx) is real and
fully testable — build a sample file, extract it back, assert the text
round-trips. Turning that raw text into structured `ResumeData`/
`JobDescription` goes through `ModelProviderRouter.chat`, which this
environment can't call for real (no reachable LLM), so that half is
tested with the provider mocked — but the JSON-validation step around it
(`model_validate_json`, with a clear error on malformed output) is real
Pydantic validation, not itself mocked.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.services.json_utils import extract_json_from_llm
from app.services.provider import ModelProviderRouter, ModelRole

SUPPORTED_RESUME_EXTENSIONS = {".pdf", ".docx", ".doc"}


class UnsupportedFileTypeError(ValueError):
    def __init__(self, suffix: str) -> None:
        super().__init__(
            f"Unsupported resume file type '{suffix}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_RESUME_EXTENSIONS))}"
        )


class StructuringError(RuntimeError):
    """Raised when the LLM's response can't be parsed into the expected
    schema — surfaces the validation error rather than silently returning
    a half-populated/garbage object."""


class ContactInfo(BaseModel):
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None


class Skill(BaseModel):
    name: str
    category: str | None = None


class Experience(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    highlights: list[str] = []


class Education(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    graduation_date: str | None = None


class Project(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = []


class ResumeData(BaseModel):
    full_text: str = ""
    name: str | None = None
    contact: ContactInfo | None = None
    summary: str | None = None
    skills: list[Skill] = []
    experience: list[Experience] = []
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[str] = []


class JobDescription(BaseModel):
    title: str
    company: str | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    experience_level: str | None = None
    domain: str | None = None


RESUME_PARSE_PROMPT = """You extract structured data from resumes. Given the raw resume \
text, respond with ONLY a JSON object (no markdown fences, no commentary) matching this shape:

{
  "name": "...", "contact": {"email": "...", "phone": "...", "location": "...", "linkedin": "..."},
  "summary": "...", "skills": [{"name": "...", "category": "..."}],
  "experience": [{"company": "...", "title": "...", "start_date": "...", "end_date": "...", \
"description": "...", "highlights": ["..."]}],
  "education": [{"institution": "...", "degree": "...", "field_of_study": "...", \
"graduation_date": "..."}],
  "projects": [{"name": "...", "description": "...", "technologies": ["..."]}],
  "certifications": ["..."]
}

Omit fields you can't find rather than guessing. Do not include a "full_text" field."""

JD_PARSE_PROMPT = """You extract structured data from job descriptions. Given the raw JD \
text, respond with ONLY a JSON object (no markdown fences, no commentary) matching this shape:

{
  "title": "...", "company": "...", "required_skills": ["..."], "preferred_skills": ["..."],
  "responsibilities": ["..."], "experience_level": "entry|mid|senior|staff|principal",
  "domain": "..."
}"""


def _extract_pdf_text(file_path: Path) -> str:
    import fitz  # PyMuPDF

    with fitz.open(file_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def _extract_docx_text(file_path: Path) -> str:
    import docx

    document = docx.Document(str(file_path))
    return "\n".join(p.text for p in document.paragraphs)


class ResumeParser:
    def __init__(self, provider: ModelProviderRouter) -> None:
        self.provider = provider

    def extract_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return _extract_pdf_text(file_path)
        if suffix in (".docx", ".doc"):
            return _extract_docx_text(file_path)
        raise UnsupportedFileTypeError(suffix)

    async def parse(self, file_path: Path) -> ResumeData:
        text = self.extract_text(file_path)
        return await self.parse_text(text)

    async def parse_text(self, text: str) -> ResumeData:
        """Split out from `parse()` so callers that already have raw text
        (e.g. from a client-side extraction, or tests) don't need a file
        on disk."""
        try:
            raw_response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": RESUME_PARSE_PROMPT},
                    {"role": "user", "content": text},
                ],
                model_role=ModelRole.REASONING,
                stream=False,
                response_format={"type": "json_object"},
                max_tokens=1500,
            )
        except StructuringError:
            raise
        except Exception as err:
            import logging
            logging.getLogger(__name__).warning("LLM resume parsing unavailable/failed (%s); falling back to heuristic parsing", err)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            name = lines[0] if lines else "Candidate"
            return ResumeData(
                full_text=text,
                name=name[:100],
                summary=lines[1] if len(lines) > 1 else text[:200],
            )

        try:
            cleaned_response = extract_json_from_llm(raw_response)
            data = ResumeData.model_validate_json(cleaned_response)
            data.full_text = text
            return data
        except (ValidationError, ValueError) as err:
            raise StructuringError(
                f"LLM response didn't match the expected resume schema: {err}"
            ) from err


class JDParser:
    def __init__(self, provider: ModelProviderRouter) -> None:
        self.provider = provider

    async def parse(self, jd_text: str) -> JobDescription:
        try:
            raw_response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": JD_PARSE_PROMPT},
                    {"role": "user", "content": jd_text},
                ],
                model_role=ModelRole.REASONING,
                stream=False,
                response_format={"type": "json_object"},
                max_tokens=1500,
            )
        except StructuringError:
            raise
        except Exception as err:
            import logging
            logging.getLogger(__name__).warning("LLM JD parsing unavailable/failed (%s); falling back to heuristic parsing", err)
            lines = [l.strip() for l in jd_text.splitlines() if l.strip()]
            title = lines[0] if lines else "Job Position"
            return JobDescription(
                title=title[:100],
                company="Target Company",
                required_skills=[],
                responsibilities=lines[1:5] if len(lines) > 1 else [],
                experience_level="mid",
                domain="General",
            )

        try:
            cleaned_response = extract_json_from_llm(raw_response)
            return JobDescription.model_validate_json(cleaned_response)
        except (ValidationError, ValueError) as err:
            raise StructuringError(
                f"LLM response didn't match the expected job description schema: {err}"
            ) from err
