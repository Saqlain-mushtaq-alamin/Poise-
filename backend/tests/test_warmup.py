"""WarmUpConductor: real, deterministic stage sequencing + LLM-backed text
generation (provider mocked)."""

from __future__ import annotations

import pytest

from app.services.ingestion import JobDescription, ResumeData
from app.services.personas import get_persona
from app.services.warmup import (
    SMALL_TALK_FLOW,
    WarmUpConductor,
    is_warm_up_complete,
    next_stage,
)


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.last_messages = None

    async def chat(self, messages, model_role=None, stream=False, **kwargs):
        self.last_messages = messages
        return self.response


def test_small_talk_flow_has_four_stages():
    assert SMALL_TALK_FLOW == ["greeting", "logistics", "ice_breaker", "role_context"]


def test_next_stage_walks_through_the_whole_flow():
    assert next_stage("greeting") == "logistics"
    assert next_stage("logistics") == "ice_breaker"
    assert next_stage("ice_breaker") == "role_context"
    assert next_stage("role_context") is None


def test_next_stage_unknown_stage_starts_from_the_top():
    assert next_stage("not-a-real-stage") == "greeting"


def test_is_warm_up_complete_only_true_at_the_end():
    assert is_warm_up_complete("greeting") is False
    assert is_warm_up_complete("ice_breaker") is False
    assert is_warm_up_complete("role_context") is True


@pytest.mark.asyncio
async def test_generate_greeting_returns_llm_text():
    provider = FakeProvider("Hi Jane, thanks so much for joining today!")
    conductor = WarmUpConductor(provider)
    persona = get_persona("professional")
    resume = ResumeData(full_text="raw", name="Jane Doe", summary="Backend engineer")
    jd = JobDescription(title="Senior Engineer", company="Acme Corp")

    greeting = await conductor.generate_greeting(persona, resume, jd)

    assert greeting == "Hi Jane, thanks so much for joining today!"
    prompt = provider.last_messages[0]["content"]
    assert "Jane Doe" in prompt
    assert "Senior Engineer" in prompt
    assert "Acme Corp" in prompt


@pytest.mark.asyncio
async def test_respond_to_small_talk_advances_the_stage():
    provider = FakeProvider("Nice! I've heard great things about that city.")
    conductor = WarmUpConductor(provider)
    persona = get_persona("friendly")

    response = await conductor.respond_to_small_talk(
        "I'm doing well, based in Austin!", current_stage="greeting", persona=persona
    )

    assert response.text == "Nice! I've heard great things about that city."
    assert response.next_stage == "logistics"
    assert response.is_complete is False


@pytest.mark.asyncio
async def test_respond_to_small_talk_signals_completion_on_final_stage():
    provider = FakeProvider("Great, let's dive into the first question.")
    conductor = WarmUpConductor(provider)
    persona = get_persona("tough")

    response = await conductor.respond_to_small_talk(
        "I love solving hard distributed-systems problems.",
        current_stage="role_context",
        persona=persona,
    )

    assert response.next_stage is None
    assert response.is_complete is True


@pytest.mark.asyncio
async def test_greeting_handles_missing_company_gracefully():
    provider = FakeProvider("Hi there!")
    conductor = WarmUpConductor(provider)
    persona = get_persona("professional")
    resume = ResumeData(full_text="raw")
    jd = JobDescription(title="Engineer")  # no company set

    await conductor.generate_greeting(persona, resume, jd)
    prompt = provider.last_messages[0]["content"]
    assert "Engineer role." in prompt or "Engineer role\n" in prompt or "Engineer role" in prompt
