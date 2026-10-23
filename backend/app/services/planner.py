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
import logging

from pydantic import BaseModel, ValidationError

from app.services.company_formats import get_company_format
from app.services.ingestion import JobDescription, ResumeData
from app.services.json_utils import extract_json_from_llm
from app.services.provider import ModelProviderRouter, ModelRole

logger = logging.getLogger("poise.planner")


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
    id: str = "q1"
    text: str = ""
    follow_ups: list[str] = []
    evaluation_criteria: list[str] = []
    difficulty: str = "medium"
    skills_tested: list[str] = []
    source: str = "jd_requirement"  # resume_gap | jd_requirement | behavioral_framework


class InterviewSection(BaseModel):
    type: str = "general"  # behavioral | technical | coding | situational
    title: str = "Interview Section"
    questions: list[PlannedQuestion] = []
    time_budget_minutes: int = 15


class InterviewPlan(BaseModel):
    sections: list[InterviewSection] = []
    estimated_duration_minutes: int = 45
    coverage_matrix: dict[str, list[str]] = {}
    is_personalized: bool = True
    warning: str | None = None


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
      "type": "behavioral|technical|coding|system_design",
      "title": "...",
      "time_budget_minutes": <int, MUST match the provided skeleton for this type>,
      "questions": [
        {{
          "id": "q1", "text": "...", "follow_ups": ["..."],
          "evaluation_criteria": ["..."], "difficulty": "{difficulty}",
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

PACING & QUESTION COUNT RULES (Strictly scale questions to time_budget_minutes):
- Behavioral sections: allocate ~4-5 minutes per question (e.g. 10m -> 2 questions, 15m -> 3 questions).
- Technical sections: allocate ~5-7 minutes per question (e.g. 10m -> 2 questions, 20m -> 3-4 questions).
- Coding sections: allocate ~12-15 minutes per problem (e.g. 15m -> 1 problem, 30m -> 2 problems).
- System design sections: allocate ~15-20 minutes per problem (e.g. 20m -> 1 problem, 35m -> 2 problems).
Generate an appropriate number of distinct questions per section to fill the allotted time budget.

DIFFICULTY CALIBRATION ({difficulty}):
- junior: Focus on foundational concepts, language syntax, clean code basics, standard algorithms, and clear requirements.
- mid: Focus on practical tradeoffs, real-world edge cases, component interaction, debugging, and independent delivery.
- senior: Focus on architectural decisions, performance bottlenecks, concurrency, resilience, and ambiguous requirements.
- lead / staff: Focus on distributed systems scale, organization-level impact, technical strategy, and failure domains.

Section time budgets (minutes): {section_budgets}
Target Difficulty: {difficulty}
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

        try:
            raw_response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model_role=ModelRole.REASONING,
                stream=False,
                response_format={"type": "json_object"},
                max_tokens=2500,
            )
        except PlanGenerationError:
            raise
        except Exception as err:
            logger.exception("LLM plan generation failed (%s); generating fallback plan", err)
            return self._generate_fallback_plan(resume, jd, config, section_budgets)

        payload = None
        cleaned_response = extract_json_from_llm(raw_response)
        try:
            payload = json.loads(cleaned_response)
        except (json.JSONDecodeError, ValueError) as json_err:
            logger.warning("Initial JSON parse failed (%s); attempting LLM repair prompt", json_err)
            try:
                repair_prompt = (
                    "Fix any JSON syntax errors in the following snippet. Output ONLY valid JSON matching the interview plan schema:\n"
                    f"```json\n{cleaned_response[:1500]}\n```"
                )
                repaired_raw = await self.provider.chat(
                    messages=[{"role": "user", "content": repair_prompt}],
                    model_role=ModelRole.REASONING,
                    stream=False,
                    response_format={"type": "json_object"},
                    max_tokens=2500,
                )
                payload = json.loads(extract_json_from_llm(repaired_raw))
            except Exception as repair_err:
                raise PlanGenerationError(
                    f"LLM response didn't match the expected interview plan schema: {json_err}"
                ) from repair_err

        try:
            if not isinstance(payload, dict):
                raise PlanGenerationError("LLM response must be a JSON object")

            sections_raw = payload.get("sections")
            if not isinstance(sections_raw, list):
                raise PlanGenerationError("LLM response 'sections' field must be a list")

            payload.setdefault(
                "estimated_duration_minutes",
                sum(s.get("time_budget_minutes", 0) for s in sections_raw if isinstance(s, dict))
                + _WARM_UP_MINUTES
                + _CLOSING_MINUTES,
            )

            plan = InterviewPlan.model_validate(payload)
            plan.is_personalized = True
            return plan
        except (ValidationError, TypeError, AttributeError) as err:
            raise PlanGenerationError(
                f"LLM response didn't match the expected interview plan schema: {err}"
            ) from err

    def _generate_fallback_plan(
        self, resume: ResumeData, jd: JobDescription, config: InterviewConfig, section_budgets: dict[str, int]
    ) -> InterviewPlan:
        sections = []
        q_idx = 1
        is_senior = config.difficulty in ("senior", "lead", "staff")

        for sec_type, budget in section_budgets.items():
            questions = []
            if sec_type == "behavioral":
                q_count = max(1, min(4, budget // 5))
                beh_prompts = [
                    (
                        f"Tell me about a high-stakes technical initiative you drove across teams for {jd.title}."
                        if is_senior
                        else f"Tell me about a challenging project you delivered relevant to {jd.title}."
                    ),
                    (
                        "Describe how you handled conflicting architectural priorities between engineering and product stakeholders."
                        if is_senior
                        else "Describe a situation where you had a disagreement with a team member. How did you resolve it?"
                    ),
                    (
                        "Tell me about a time you mentored engineers through a significant architectural migration."
                        if is_senior
                        else "Tell me about a time you had to learn a new technology or domain quickly under tight deadlines."
                    ),
                ]
                for i in range(q_count):
                    prompt_text = beh_prompts[i % len(beh_prompts)]
                    questions.append(
                        PlannedQuestion(
                            id=f"q{q_idx}",
                            text=prompt_text,
                            follow_ups=["What was your specific ownership?", "How did you measure impact?"],
                            evaluation_criteria=["Clarity", "STAR method", "Strategic Ownership" if is_senior else "Ownership"],
                            difficulty=config.difficulty,
                            skills_tested=["Communication", "Collaboration", "Leadership" if is_senior else "Problem Solving"],
                            source="behavioral_framework",
                        )
                    )
                    q_idx += 1

            elif sec_type == "technical":
                q_count = max(1, min(5, budget // 6))
                skills = jd.required_skills or ["System Architecture", "Performance", "Data Modeling"]
                for i in range(q_count):
                    skill = skills[i % len(skills)]
                    if is_senior:
                        q_text = f"In complex production environments using {skill}, how do you evaluate tradeoffs between latency, consistency, and operational simplicity?"
                        eval_crit = ["Architectural Depth", "Trade-off Analysis", "Failure Modes"]
                    else:
                        q_text = f"Can you explain core technical principles and best practices when working with {skill}?"
                        eval_crit = ["Technical Accuracy", "Practical Application", "Problem Solving"]
                    questions.append(
                        PlannedQuestion(
                            id=f"q{q_idx}",
                            text=q_text,
                            follow_ups=["What trade-offs do you consider?", "How would you diagnose failures in production?"],
                            evaluation_criteria=eval_crit,
                            difficulty=config.difficulty,
                            skills_tested=[skill],
                            source="jd_requirement",
                        )
                    )
                    q_idx += 1

            elif sec_type == "coding":
                q_count = max(1, min(3, budget // 14))
                coding_prompts = [
                    (
                        "Design and implement an in-memory rate limiter supporting burst traffic with minimal memory overhead."
                        if is_senior
                        else "Write an efficient algorithm to process and aggregate streaming data under memory constraints."
                    ),
                    (
                        "Implement a concurrent task scheduler with priority execution and dependency resolution."
                        if is_senior
                        else "Implement a caching layer with LRU eviction and thread-safe operations."
                    ),
                ]
                for i in range(q_count):
                    questions.append(
                        PlannedQuestion(
                            id=f"q{q_idx}",
                            text=coding_prompts[i % len(coding_prompts)],
                            follow_ups=["What is the runtime time and space complexity?", "How does this scale under concurrency?"],
                            evaluation_criteria=["Code Correctness", "Complexity Analysis", "Concurrency Safety" if is_senior else "Edge Cases"],
                            difficulty=config.difficulty,
                            skills_tested=["Data Structures", "Algorithms", "Concurrency"],
                            source="jd_requirement",
                        )
                    )
                    q_idx += 1

            elif sec_type == "system_design":
                q_count = max(1, min(2, budget // 18))
                design_prompts = [
                    f"Design a globally distributed, fault-tolerant {jd.title} system handling 100,000 requests/sec with 99.99% availability.",
                    f"Design a scalable real-time event streaming and analytical pipeline for {jd.title}.",
                ]
                for i in range(q_count):
                    questions.append(
                        PlannedQuestion(
                            id=f"q{q_idx}",
                            text=design_prompts[i % len(design_prompts)],
                            follow_ups=["How do you handle partition tolerance?", "Where are the primary failure bottlenecks?"],
                            evaluation_criteria=["Distributed Architecture", "Reliability", "Scalability"],
                            difficulty=config.difficulty,
                            skills_tested=["Distributed Systems", "High Availability", "Architecture"],
                            source="jd_requirement",
                        )
                    )
                    q_idx += 1

            sections.append(
                InterviewSection(
                    type=sec_type,
                    title=f"{sec_type.replace('_', ' ').title()} Round",
                    questions=questions,
                    time_budget_minutes=budget,
                )
            )

        return InterviewPlan(
            sections=sections,
            estimated_duration_minutes=config.duration_minutes,
            coverage_matrix={"General": [f"q{i}" for i in range(1, q_idx)]},
            is_personalized=False,
            warning="Could not personalize interview questions using AI; loaded structured questions scaled to your duration and difficulty.",
        )
