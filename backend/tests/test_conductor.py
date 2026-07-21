"""InterviewConductor: persona-flavored delivery + reaction picking are
real, seedable, deterministic logic; evaluation/follow-up generation are
tested with the LLM provider mocked."""

from __future__ import annotations

import json
import random

import pytest

from app.services.conductor import (
    FOLLOW_UP_SCORE_THRESHOLD,
    InterviewConductor,
    pick_reaction,
)
from app.services.personas import get_persona
from app.services.planner import PlannedQuestion


class FakeProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, model_role=None, stream=False, **kwargs):
        self.calls.append(messages)
        return self._responses.pop(0)


def _question(**overrides) -> PlannedQuestion:
    defaults = dict(
        id="q1",
        text="Tell me about a challenging project.",
        evaluation_criteria=["specificity", "ownership"],
        skills_tested=[],
        source="jd_requirement",
    )
    defaults.update(overrides)
    return PlannedQuestion(**defaults)


class TestPickReaction:
    def test_strong_score_picks_from_strong_band(self):
        rng = random.Random(42)
        reaction = pick_reaction(0.9, rng)
        assert reaction in ["Interesting.", "That's a great example.", "I like that."]

    def test_weak_score_picks_from_weak_band(self):
        rng = random.Random(42)
        reaction = pick_reaction(0.1, rng)
        assert reaction in ["I see.", "Alright.", "Understood."]

    def test_deterministic_with_a_seeded_rng(self):
        r1 = pick_reaction(0.9, random.Random(7))
        r2 = pick_reaction(0.9, random.Random(7))
        assert r1 == r2


class TestDeliverQuestion:
    def test_wraps_question_with_a_persona_transition(self):
        conductor = InterviewConductor(provider=FakeProvider([]), rng=random.Random(1))
        persona = get_persona("professional")
        delivery = conductor.deliver_question(_question(), persona)

        assert "Tell me about a challenging project." in delivery.text
        assert delivery.question_id == "q1"
        assert delivery.is_follow_up is False

    def test_follow_up_uses_a_different_phrase_bank(self):
        conductor = InterviewConductor(provider=FakeProvider([]), rng=random.Random(1))
        persona = get_persona("tough")
        delivery = conductor.deliver_question(_question(), persona, is_follow_up=True)
        assert delivery.is_follow_up is True

    def test_unknown_persona_id_falls_back_to_default_transitions(self):
        conductor = InterviewConductor(provider=FakeProvider([]), rng=random.Random(1))
        from app.services.personas import Persona

        weird_persona = Persona(
            id="unknown-style", name="Test", style="", voice="", system_prompt="x"
        )
        delivery = conductor.deliver_question(_question(), weird_persona)
        assert "Tell me about a challenging project." in delivery.text


class TestProcessAnswer:
    @pytest.mark.asyncio
    async def test_high_score_no_gaps_moves_to_next_question(self):
        provider = FakeProvider(
            [json.dumps({"score": 0.9, "feedback": "Great answer", "gaps": []})]
        )
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))

        result = await conductor.process_answer("A very thorough answer...", _question())

        assert result.next_action == "next_question"
        assert result.follow_up_question is None
        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_low_score_with_gaps_triggers_a_follow_up(self):
        provider = FakeProvider(
            [
                json.dumps(
                    {"score": 0.4, "feedback": "Missing specifics", "gaps": ["no concrete result"]}
                ),
                "What was the measurable outcome of that project?",
            ]
        )
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))

        result = await conductor.process_answer("I worked on something.", _question())

        assert result.next_action == "follow_up"
        assert result.follow_up_question == "What was the measurable outcome of that project?"
        assert result.score == 0.4

    @pytest.mark.asyncio
    async def test_low_score_but_no_gaps_does_not_force_a_follow_up(self):
        # A low score with an empty gaps list means "just weak", not
        # "there's a specific thing to probe" — don't fabricate a follow-up.
        provider = FakeProvider(
            [json.dumps({"score": 0.3, "feedback": "Generally weak", "gaps": []})]
        )
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))

        result = await conductor.process_answer("meh", _question())

        assert result.next_action == "next_question"

    @pytest.mark.asyncio
    async def test_score_at_threshold_boundary_does_not_trigger_follow_up(self):
        provider = FakeProvider(
            [json.dumps({"score": FOLLOW_UP_SCORE_THRESHOLD, "feedback": "ok", "gaps": ["x"]})]
        )
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))

        result = await conductor.process_answer("answer", _question())
        assert result.next_action == "next_question"  # strictly less-than triggers follow-up

    @pytest.mark.asyncio
    async def test_framework_analysis_runs_for_behavioral_questions(self):
        provider = FakeProvider([json.dumps({"score": 0.9, "feedback": "Good", "gaps": []})])
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))
        question = _question(source="behavioral_framework")

        result = await conductor.process_answer(
            "At my last job we had an outage. My task was to fix it. So I rolled back the "
            "deploy. As a result, downtime dropped to minutes.",
            question,
        )

        assert result.framework_analysis is not None
        assert result.framework_analysis.components_present["result"] is True

    @pytest.mark.asyncio
    async def test_framework_analysis_skipped_for_non_behavioral_questions(self):
        provider = FakeProvider([json.dumps({"score": 0.9, "feedback": "Good", "gaps": []})])
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))

        result = await conductor.process_answer(
            "A technical answer.", _question(source="jd_requirement")
        )

        assert result.framework_analysis is None

    @pytest.mark.asyncio
    async def test_reaction_is_always_set(self):
        provider = FakeProvider([json.dumps({"score": 0.5, "feedback": "ok", "gaps": []})])
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))
        result = await conductor.process_answer("answer", _question())
        assert result.reaction is not None

    @pytest.mark.asyncio
    async def test_follow_up_prompt_includes_the_identified_gaps(self):
        provider = FakeProvider(
            [
                json.dumps(
                    {"score": 0.2, "feedback": "weak", "gaps": ["missing metrics", "no timeline"]}
                ),
                "Follow-up text",
            ]
        )
        conductor = InterviewConductor(provider=provider, rng=random.Random(1))

        await conductor.process_answer("vague answer", _question())

        follow_up_prompt = provider.calls[1][0]["content"]
        assert "missing metrics" in follow_up_prompt
        assert "no timeline" in follow_up_prompt
