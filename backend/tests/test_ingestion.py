"""Resume/JD ingestion: real PDF/DOCX text extraction (built and read back
with PyMuPDF/python-docx directly, no LLM involved) plus LLM-structuring
orchestration with the provider mocked."""

from __future__ import annotations

import json

import pytest

from app.services.ingestion import (
    JDParser,
    JobDescription,
    ResumeData,
    ResumeParser,
    StructuringError,
    UnsupportedFileTypeError,
)


def _make_pdf(tmp_path, text: str):
    import fitz

    path = tmp_path / "resume.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


def _make_docx(tmp_path, paragraphs: list[str]):
    import docx

    path = tmp_path / "resume.docx"
    document = docx.Document()
    for para in paragraphs:
        document.add_paragraph(para)
    document.save(str(path))
    return path


class FakeProvider:
    """Stands in for ModelProviderRouter — returns whatever JSON string is
    configured, so ingestion's parsing/validation logic is exercised for
    real without needing a reachable LLM."""

    def __init__(self, response: str):
        self.response = response
        self.last_messages = None

    async def chat(self, messages, model_role=None, stream=False, **kwargs):
        self.last_messages = messages
        return self.response


def test_extract_pdf_text_round_trips(tmp_path):
    pdf_path = _make_pdf(tmp_path, "Jane Doe - Software Engineer")
    parser = ResumeParser(provider=FakeProvider("{}"))

    text = parser.extract_text(pdf_path)
    assert "Jane Doe" in text
    assert "Software Engineer" in text


def test_extract_docx_text_round_trips(tmp_path):
    docx_path = _make_docx(tmp_path, ["Jane Doe", "Software Engineer", "5 years experience"])
    parser = ResumeParser(provider=FakeProvider("{}"))

    text = parser.extract_text(docx_path)
    assert "Jane Doe" in text
    assert "5 years experience" in text


def test_extract_text_rejects_unsupported_file_type(tmp_path):
    txt_path = tmp_path / "resume.txt"
    txt_path.write_text("hello")
    parser = ResumeParser(provider=FakeProvider("{}"))

    with pytest.raises(UnsupportedFileTypeError):
        parser.extract_text(txt_path)


@pytest.mark.asyncio
async def test_parse_text_structures_via_the_provider_and_validates_schema():
    payload = {
        "name": "Jane Doe",
        "contact": {"email": "jane@example.com"},
        "summary": "Senior backend engineer",
        "skills": [{"name": "Python", "category": "language"}],
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Senior Engineer",
                "start_date": "2020",
                "end_date": "Present",
                "highlights": ["Led migration to microservices"],
            }
        ],
        "education": [{"institution": "State University", "degree": "BS Computer Science"}],
        "projects": [],
        "certifications": [],
    }
    provider = FakeProvider(json.dumps(payload))
    parser = ResumeParser(provider=provider)

    result = await parser.parse_text("Jane Doe resume raw text here")

    assert isinstance(result, ResumeData)
    assert result.name == "Jane Doe"
    assert result.contact.email == "jane@example.com"
    assert result.experience[0].company == "Acme Corp"
    # full_text always reflects the real extracted text, not whatever
    # (if anything) the LLM echoed back.
    assert result.full_text == "Jane Doe resume raw text here"


@pytest.mark.asyncio
async def test_parse_text_raises_clear_error_on_malformed_llm_json():
    provider = FakeProvider("not valid json at all")
    parser = ResumeParser(provider=provider)

    with pytest.raises(StructuringError):
        await parser.parse_text("some resume text")


@pytest.mark.asyncio
async def test_parse_text_raises_clear_error_on_schema_mismatch():
    # Valid JSON, but "experience" entries are missing the required "title" field.
    payload = {"experience": [{"company": "Acme"}]}
    provider = FakeProvider(json.dumps(payload))
    parser = ResumeParser(provider=provider)

    with pytest.raises(StructuringError):
        await parser.parse_text("some resume text")


@pytest.mark.asyncio
async def test_parse_pdf_end_to_end_with_mocked_provider(tmp_path):
    pdf_path = _make_pdf(tmp_path, "Jane Doe - Backend Engineer with 5 years experience")
    provider = FakeProvider(json.dumps({"name": "Jane Doe"}))
    parser = ResumeParser(provider=provider)

    result = await parser.parse(pdf_path)
    assert result.name == "Jane Doe"
    assert "Backend Engineer" in result.full_text


@pytest.mark.asyncio
async def test_jd_parser_structures_via_the_provider():
    payload = {
        "title": "Senior Backend Engineer",
        "company": "Acme Corp",
        "required_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Kubernetes"],
        "responsibilities": ["Design APIs", "Mentor juniors"],
        "experience_level": "senior",
        "domain": "fintech",
    }
    provider = FakeProvider(json.dumps(payload))
    parser = JDParser(provider=provider)

    result = await parser.parse("We are looking for a Senior Backend Engineer...")

    assert isinstance(result, JobDescription)
    assert result.title == "Senior Backend Engineer"
    assert "Python" in result.required_skills


@pytest.mark.asyncio
async def test_jd_parser_raises_clear_error_on_malformed_json():
    provider = FakeProvider("nonsense")
    parser = JDParser(provider=provider)

    with pytest.raises(StructuringError):
        await parser.parse("some JD text")


@pytest.mark.asyncio
async def test_resume_parser_sends_the_extracted_text_to_the_provider():
    provider = FakeProvider(json.dumps({"name": "Test"}))
    parser = ResumeParser(provider=provider)

    await parser.parse_text("unique-marker-text-12345")

    assert provider.last_messages is not None
    assert any("unique-marker-text-12345" in m["content"] for m in provider.last_messages)
