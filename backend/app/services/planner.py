"""Interview plan generation, per the Phase 4 spec's §4.2.

Section time-budgeting is real, deterministic logic (splitting a total
duration across whichever section types are enabled) — that's what
`default_section_time_budgets` is, and it's independently tested without
any LLM involved. Turning that skeleton into actual, resume/JD-grounded
questions requires an LLM call this environment can't make for real, so
`generate_plan` is tested with the provider mocked, same pattern as
ingestion.py.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from app.services.company_formats import get_company_format
from app.services.ingestion import JobDescription, ResumeData
from app.services.provider import ModelProviderRouter, ModelRole


class InterviewConfig(BaseModel):
    duration_minutes: int = 45
    include_behavioral: bool = True
    include_technical: bool = True
    include_coding: bool = True
    include_system_design: bool = False
    difficulty: str = "medium"  # easy | medium | hard
    persona: str = "professional"
    company_format: str | None = None


class PlannedQuestion(BaseModel):
    id: str
    text: str
    follow_ups: list[str] = []
    evaluation_criteria: list[str] = []
    difficulty: str = "medium"
    skills_tested: list[str] = []
    source: str = "jd_requirement"  # resume_gap | jd_requirement | behavioral_framework


class InterviewSection(BaseModel):
    type: str  # behavioral | technical | coding | situational
    title: str
    questions: list[PlannedQuestion] = []
    time_budget_minutes: int


class InterviewPlan(BaseModel):
    sections: list[InterviewSection]
    estimated_duration_minutes: int
    coverage_matrix: dict[str, list[str]] = {}


class PlanGenerationError(RuntimeError):
    pass


# Relative weight each section type gets when splitting the total duration
# — technical/coding get more room since they typically take longer per
# question than a behavioral prompt does.
_SECTION_WEIGHTS = {
    "behavioral": 1.0,
    "technical": 1.4,
    "coding": 1.8,
    "system_design": 1.6,
}

_WARM_UP_MINUTES = 3
_CLOSING_MINUTES = 2


def default_section_time_budgets(config: InterviewConfig) -> dict[str, int]:
    """Deterministically splits `config.duration_minutes` across whichever
    section types are enabled, reserving a fixed slice for warm-up and
    closing. Pure function — no LLM, no I/O — so the planner's skeleton is
    correct before a single token gets generated.

    Uses the largest-remainder method: floor each section's proportional
    share, then hand out whatever whole minutes are left over to the
    sections with the biggest fractional remainder. That guarantees the
    budgets always sum to exactly the available time and every enabled
    section gets at least 1 minute — a floor-then-patch-the-drift approach
    can go negative when the total time is too tight to give everyone 3+
    minutes, which a 10-minute interview with three sections enabled
    genuinely is.
    """
    enabled: list[str] = []
    if config.include_behavioral:
        enabled.append("behavioral")
    if config.include_technical:
        enabled.append("technical")
    if config.include_coding:
        enabled.append("coding")
    if config.include_system_design:
        enabled.append("system_design")

    if not enabled:
        return {}

    available_minutes = max(
        config.duration_minutes - _WARM_UP_MINUTES - _CLOSING_MINUTES, len(enabled)
    )
    total_weight = sum(_SECTION_WEIGHTS[s] for s in enabled)

    raw_shares = {s: available_minutes * _SECTION_WEIGHTS[s] / total_weight for s in enabled}
    budgets = {s: max(int(raw_shares[s]), 1) for s in enabled}

    remainder = available_minutes - sum(budgets.values())
    by_fractional_part_desc = sorted(
        enabled, key=lambda s: raw_shares[s] - int(raw_shares[s]), reverse=True
    )
    i = 0
    while remainder > 0:
        section = by_fractional_part_desc[i % len(by_fractional_part_desc)]
        budgets[section] += 1
        remainder -= 1
        i += 1

    return budgets


PLAN_GENERATION_PROMPT = """You are an expert technical interview designer. Given a \
candidate's resume, a job description, and a section time-budget skeleton, generate a \
tailored interview plan. Respond with ONLY a JSON object (no markdown fences, no \
commentary) matching this shape:

{{
  "sections": [
    {{
      "type": "behavioral|technical|coding|situational",
      "title": "...",
      "time_budget_minutes": <int, MUST match the provided skeleton for this type>,
      "questions": [
        {{
          "id": "q1", "text": "...", "follow_ups": ["..."],
          "evaluation_criteria": ["..."], "difficulty": "easy|medium|hard",
          "skills_tested": ["..."], "source": "resume_gap|jd_requirement|behavioral_framework"
        }}
      ]
    }}
  ],
  "coverage_matrix": {{"skill_name": ["q1", "q3"]}}
}}

Ground every question in specifics from the resume and JD below — reference actual \
technologies, projects, or requirements. Do not write generic questions that could apply \
to any candidate.

Section time budgets (minutes): {section_budgets}
Difficulty: {difficulty}
Company format: {company_format_note}

RESUME SUMMARY:
{resume_summary}

JOB DESCRIPTION:
{jd_summary}"""


def _resume_summary(resume: ResumeData) -> str:
    lines = [f"Summary: {resume.summary or 'n/a'}"]
    if resume.skills:
        lines.append("Skills: " + ", ".join(s.name for s in resume.skills))
    for exp in resume.experience:
        lines.append(f"- {exp.title} at {exp.company}: {exp.description or ''}")
    return "\n".join(lines)


def _jd_summary(jd: JobDescription) -> str:
    lines = [f"Title: {jd.title}", f"Level: {jd.experience_level or 'n/a'}"]
    if jd.required_skills:
        lines.append("Required skills: " + ", ".join(jd.required_skills))
    if jd.responsibilities:
        lines.append("Responsibilities: " + "; ".join(jd.responsibilities))
    return "\n".join(lines)


class InterviewPlanner:
    def __init__(self, provider: ModelProviderRouter) -> None:
        self.provider = provider

    async def generate_plan(
        self, resume: ResumeData, jd: JobDescription, config: InterviewConfig
    ) -> InterviewPlan:
        section_budgets = default_section_time_budgets(config)
        if not section_budgets:
            raise PlanGenerationError(
                "No section types enabled in InterviewConfig — nothing to plan."
            )

        company_format_note = "None specified — use a general structured format."
        if config.company_format:
            fmt = get_company_format(config.company_format)
            company_format_note = f"{fmt.name}: {fmt.framework}"

        prompt = PLAN_GENERATION_PROMPT.format(
            section_budgets=json.dumps(section_budgets),
            difficulty=config.difficulty,
            company_format_note=company_format_note,
            resume_summary=_resume_summary(resume),
            jd_summary=_jd_summary(jd),
        )

        raw_response = await self.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model_role=ModelRole.REASONING,
            stream=False,
        )

        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as err:
            raise PlanGenerationError(f"LLM response was not valid JSON: {err}") from err

        payload.setdefault(
            "estimated_duration_minutes",
            sum(s.get("time_budget_minutes", 0) for s in payload.get("sections", []))
            + _WARM_UP_MINUTES
            + _CLOSING_MINUTES,
        )

        try:
            return InterviewPlan.model_validate(payload)
        except ValidationError as err:
            raise PlanGenerationError(
                f"LLM response didn't match the expected interview plan schema: {err}"
            ) from err
