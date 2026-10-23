"""InterviewPlanner: real, deterministic time-budget splitting (no LLM)
plus LLM-backed plan generation with the provider mocked."""

from __future__ import annotations

import json

import pytest

from app.services.ingestion import Experience, JobDescription, ResumeData, Skill
from app.services.planner import (
    InterviewConfig,
    InterviewPlan,
    InterviewPlanner,
    PlanGenerationError,
    default_section_time_budgets,
)


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.last_messages = None

    async def chat(self, messages, model_role=None, stream=False, **kwargs):
        self.last_messages = messages
        return self.response


def _resume() -> ResumeData:
    return ResumeData(
        full_text="raw",
        name="Jane Doe",
        summary="Backend engineer with 5 years of Python experience",
        skills=[Skill(name="Python"), Skill(name="PostgreSQL")],
        experience=[
            Experience(company="Acme", title="Senior Engineer", description="Led migrations")
        ],
    )


def _jd() -> JobDescription:
    return JobDescription(
        title="Senior Backend Engineer",
        required_skills=["Python", "PostgreSQL"],
        responsibilities=["Design APIs"],
        experience_level="senior",
    )


class TestDefaultSectionTimeBudgets:
    def test_only_enabled_sections_appear(self):
        config = InterviewConfig(
            include_behavioral=True,
            include_technical=False,
            include_coding=False,
            include_system_design=False,
        )
        budgets = default_section_time_budgets(config)
        assert set(budgets.keys()) == {"behavioral"}

    def test_all_sections_enabled(self):
        config = InterviewConfig(
            include_behavioral=True,
            include_technical=True,
            include_coding=True,
            include_system_design=True,
        )
        budgets = default_section_time_budgets(config)
        assert set(budgets.keys()) == {"behavioral", "technical", "coding", "system_design"}

    def test_budgets_sum_to_available_time_minus_warmup_and_closing(self):
        config = InterviewConfig(duration_minutes=60)
        budgets = default_section_time_budgets(config)
        # 60 - 3 (warm-up) - 2 (closing) = 55
        assert sum(budgets.values()) == 55

    def test_no_sections_enabled_returns_empty(self):
        config = InterviewConfig(
            include_behavioral=False,
            include_technical=False,
            include_coding=False,
            include_system_design=False,
        )
        assert default_section_time_budgets(config) == {}

    def test_coding_gets_more_time_than_behavioral_at_equal_weight_base(self):
        config = InterviewConfig(
            duration_minutes=90,
            include_behavioral=True,
            include_technical=False,
            include_coding=True,
        )
        budgets = default_section_time_budgets(config)
        assert budgets["coding"] > budgets["behavioral"]

    def test_every_enabled_section_gets_at_least_one_minute(self):
        config = InterviewConfig(duration_minutes=10)  # very tight budget, 3 sections enabled
        budgets = default_section_time_budgets(config)
        assert all(v >= 1 for v in budgets.values())
        assert sum(budgets.values()) == max(10 - 3 - 2, len(budgets))

    def test_short_duration_does_not_go_negative(self):
        config = InterviewConfig(duration_minutes=1)
        budgets = default_section_time_budgets(config)
        assert all(v > 0 for v in budgets.values())

    @pytest.mark.parametrize("duration", [5, 10, 15, 30, 45, 60, 90, 120])
    def test_budgets_always_sum_exactly_regardless_of_duration(self, duration):
        config = InterviewConfig(duration_minutes=duration)
        budgets = default_section_time_budgets(config)
        expected_available = max(duration - 3 - 2, len(budgets))
        assert sum(budgets.values()) == expected_available


@pytest.mark.asyncio
async def test_generate_plan_builds_a_valid_plan_from_mocked_llm():
    plan_json = {
        "sections": [
            {
                "type": "behavioral",
                "title": "Behavioral",
                "time_budget_minutes": 10,
                "questions": [
                    {
                        "id": "q1",
                        "text": "Tell me about a time you led a migration, like at Acme.",
                        "evaluation_criteria": ["ownership", "communication"],
                        "skills_tested": ["leadership"],
                        "source": "resume_gap",
                    }
                ],
            }
        ],
        "coverage_matrix": {"leadership": ["q1"]},
    }
    provider = FakeProvider(json.dumps(plan_json))
    planner = InterviewPlanner(provider)
    config = InterviewConfig(include_behavioral=True, include_technical=False, include_coding=False)

    plan = await planner.generate_plan(_resume(), _jd(), config)

    assert isinstance(plan, InterviewPlan)
    assert plan.sections[0].questions[0].text.startswith("Tell me about")
    assert plan.estimated_duration_minutes > 0


@pytest.mark.asyncio
async def test_generate_plan_references_actual_resume_and_jd_content_in_the_prompt():
    provider = FakeProvider(json.dumps({"sections": []}))
    planner = InterviewPlanner(provider)
    config = InterviewConfig(include_behavioral=True, include_technical=False, include_coding=False)

    await planner.generate_plan(_resume(), _jd(), config)

    prompt_text = provider.last_messages[0]["content"]
    assert "Acme" in prompt_text
    assert "Senior Backend Engineer" in prompt_text


@pytest.mark.asyncio
async def test_generate_plan_raises_clear_error_on_invalid_json():
    provider = FakeProvider("not json")
    planner = InterviewPlanner(provider)
    config = InterviewConfig(include_behavioral=True, include_technical=False, include_coding=False)

    with pytest.raises(PlanGenerationError):
        await planner.generate_plan(_resume(), _jd(), config)


@pytest.mark.asyncio
async def test_generate_plan_raises_clear_error_on_schema_mismatch():
    provider = FakeProvider(
        json.dumps({"sections": "not_a_list"})
    )
    planner = InterviewPlanner(provider)
    config = InterviewConfig(include_behavioral=True, include_technical=False, include_coding=False)

    with pytest.raises(PlanGenerationError):
        await planner.generate_plan(_resume(), _jd(), config)


@pytest.mark.asyncio
async def test_generate_plan_raises_when_no_sections_enabled():
    provider = FakeProvider(json.dumps({"sections": []}))
    planner = InterviewPlanner(provider)
    config = InterviewConfig(
        include_behavioral=False,
        include_technical=False,
        include_coding=False,
        include_system_design=False,
    )

    with pytest.raises(PlanGenerationError):
        await planner.generate_plan(_resume(), _jd(), config)


@pytest.mark.asyncio
async def test_generate_plan_includes_company_format_context_when_specified():
    provider = FakeProvider(json.dumps({"sections": []}))
    planner = InterviewPlanner(provider)
    config = InterviewConfig(
        include_behavioral=True,
        include_technical=False,
        include_coding=False,
        company_format="amazon",
    )

    await planner.generate_plan(_resume(), _jd(), config)

    prompt_text = provider.last_messages[0]["content"]
    assert "Leadership Principles" in prompt_text


@pytest.mark.asyncio
async def test_generate_plan_with_thinking_model_tags_extracts_cleanly():
    """Verify that models emitting <think>...</think> tags parse successfully."""
    plan_json = {
        "sections": [
            {
                "type": "behavioral",
                "title": "Behavioral Round",
                "time_budget_minutes": 15,
                "questions": [
                    {
                        "id": "q1",
                        "text": "Tell me about leading the migrations at Acme.",
                        "evaluation_criteria": ["Leadership"],
                        "skills_tested": ["Python"],
                        "source": "resume_gap",
                    }
                ],
            }
        ],
        "coverage_matrix": {"Python": ["q1"]},
    }
    raw_with_think = f"""<think>
We need to generate a valid plan for Jane Doe.
Let me check the JD: Senior Backend Engineer.
{{ "internal_notes": "skip this brace" }}
</think>
```json
{json.dumps(plan_json)}
```"""
    provider = FakeProvider(raw_with_think)
    planner = InterviewPlanner(provider)
    config = InterviewConfig(include_behavioral=True, include_technical=False, include_coding=False)

    plan = await planner.generate_plan(_resume(), _jd(), config)
    assert plan.is_personalized is True
    assert plan.sections[0].questions[0].text == "Tell me about leading the migrations at Acme."


@pytest.mark.asyncio
async def test_generate_plan_fallback_contains_warning_and_not_personalized():
    """When the LLM fails completely, the fallback plan must flag is_personalized=False and include a warning."""
    class FailingProvider:
        async def chat(self, *args, **kwargs):
            raise RuntimeError("Connection refused")

    planner = InterviewPlanner(FailingProvider())
    config = InterviewConfig(include_behavioral=True, include_technical=True, include_coding=False)

    plan = await planner.generate_plan(_resume(), _jd(), config)
    assert plan.is_personalized is False
    assert plan.warning is not None
    assert "Could not personalize" in plan.warning
    assert len(plan.sections) == 2


@pytest.mark.asyncio
async def test_generate_plan_recovers_via_json_repair():
    """When the first response has invalid JSON syntax, repair prompt fixes it."""
    valid_plan = {
        "sections": [
            {
                "type": "technical",
                "title": "Technical",
                "time_budget_minutes": 20,
                "questions": [
                    {
                        "id": "q1",
                        "text": "How do you optimize PostgreSQL queries?",
                        "evaluation_criteria": ["Indexing"],
                        "skills_tested": ["PostgreSQL"],
                        "source": "jd_requirement",
                    }
                ],
            }
        ],
        "coverage_matrix": {"PostgreSQL": ["q1"]},
    }
    # First response has a broken JSON with unmatched brace
    class RepairingProvider:
        def __init__(self):
            self.call_count = 0

        async def chat(self, *args, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                return '{"sections": [{"type": "technical", "title": "Technical"'  # unclosed
            return json.dumps(valid_plan)

    planner = InterviewPlanner(RepairingProvider())
    config = InterviewConfig(include_behavioral=False, include_technical=True, include_coding=False)

    plan = await planner.generate_plan(_resume(), _jd(), config)
    assert plan.is_personalized is True
    assert plan.sections[0].questions[0].text == "How do you optimize PostgreSQL queries?"

