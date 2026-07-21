"""Company-specific interview formats, per the Phase 4 spec's §4.3d.

Static structural data (what rounds a given company's loop tends to have,
in what order) — the planner (planner.py) uses this to shape
`InterviewPlan.sections` before handing individual questions off to the
LLM to actually write. No LLM dependency in this module itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompanyFormat:
    id: str
    name: str
    structure: list[str]
    framework: str
    scoring_note: str
    principles: list[str] = field(default_factory=list)


COMPANY_FORMATS: dict[str, CompanyFormat] = {
    "amazon": CompanyFormat(
        id="amazon",
        name="Amazon Leadership Principles",
        structure=["lp_behavioral", "technical", "system_design", "bar_raiser"],
        framework="Each question maps to 1-2 Leadership Principles",
        scoring_note="Evaluates against specific LP criteria, not generic rubrics",
        principles=[
            "Customer Obsession",
            "Ownership",
            "Invent and Simplify",
            "Are Right, A Lot",
            "Learn and Be Curious",
            "Hire and Develop the Best",
            "Insist on the Highest Standards",
            "Think Big",
            "Bias for Action",
            "Frugality",
            "Earn Trust",
            "Dive Deep",
            "Have Backbone; Disagree and Commit",
            "Deliver Results",
        ],
    ),
    "google": CompanyFormat(
        id="google",
        name="Google Structured Interview",
        structure=["behavioral", "coding", "coding", "system_design", "googleyness"],
        framework="Structured scoring rubric per question",
        scoring_note="Emphasis on problem-solving process, not just the final answer",
    ),
    "meta": CompanyFormat(
        id="meta",
        name="Meta Interview Loop",
        structure=["behavioral", "coding", "system_design", "product_sense"],
        framework="Loop-based, each round scored independently then synthesized",
        scoring_note="Product sense round is distinctive — evaluates judgment, not just code",
    ),
    "startup": CompanyFormat(
        id="startup",
        name="Startup Conversational",
        structure=["culture_fit", "technical_deep_dive", "live_problem_solving"],
        framework="Less structured, more conversational, tests ownership",
        scoring_note="Weighs adaptability and ownership more heavily than process adherence",
    ),
    "consulting": CompanyFormat(
        id="consulting",
        name="Case Interview",
        structure=["fit", "case_study", "case_study", "behavioral"],
        framework="Case-based structured problem solving",
        scoring_note="Evaluates structuring, quantitative reasoning, and communication",
    ),
}

DEFAULT_FORMAT_ID = "startup"


class UnknownCompanyFormatError(ValueError):
    pass


def get_company_format(format_id: str) -> CompanyFormat:
    try:
        return COMPANY_FORMATS[format_id]
    except KeyError as err:
        available = ", ".join(sorted(COMPANY_FORMATS))
        raise UnknownCompanyFormatError(
            f"Unknown company format '{format_id}'. Available: {available}"
        ) from err


def list_company_formats() -> list[CompanyFormat]:
    return list(COMPANY_FORMATS.values())
