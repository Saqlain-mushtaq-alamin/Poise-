"""Tests for IELTSSessionConductor: verifies Part 3 follow-up progression and timeout."""

from __future__ import annotations

import unittest.mock as mock
import pytest

from app.models.ielts import IELTSSession
from app.services.ielts.conductor import IELTSSessionConductor
from app.services.ielts.state_machine import IELTSState, IELTSStateMachine


class FakeLLMClient:
    def __init__(self, followup_response: str = "Why do you feel that way?"):
        self.followup_response = followup_response
        self.generate_followup_calls: list[tuple] = []

    async def generate_followup(self, answer: str, part: int, theme: str) -> str:
        self.generate_followup_calls.append((answer, part, theme))
        return self.followup_response


@pytest.mark.asyncio
async def test_part3_followup_does_not_skip_bank_questions():
    """When a dynamic follow-up is generated in Part 3, the candidate answers the

    follow-up first, and the conductor then proceeds to the next bank question
    instead of skipping it.
    """
    mock_db = mock.MagicMock()
    fake_llm = FakeLLMClient("Follow-up question?")
    conductor = IELTSSessionConductor(db=mock_db, llm_client=fake_llm)

    row = IELTSSession(
        id="ielts-123",
        status=IELTSState.PART3_DISCUSSION.value,
        part3_index=0,
        part3_questions=["Bank Q0: Traffic", "Bank Q1: Public transport", "Bank Q2: Urban planning"],
        part2_cue_card={"theme": "transport"},
    )
    machine = IELTSStateMachine(IELTSState.PART3_DISCUSSION)

    # First turn: Candidate answers Bank Q0.
    # Force random < 0.4 to trigger follow-up generation.
    with mock.patch("random.random", return_value=0.1):
        prompt = await conductor._advance_after_answer(row, machine, "My answer to Q0")

    # A follow-up should have been generated and set on the row.
    assert row.dynamic_followup == "Follow-up question?"
    # part3_index must NOT have advanced yet, because the candidate was asked a followup for Q0.
    assert row.part3_index == 0
    # The prompt returned to candidate is the follow-up question.
    assert prompt.question == "Follow-up question?"

    # The candidate now answers the follow-up question.
    prompt2 = await conductor._advance_after_answer(row, machine, "My answer to followup")

    # The dynamic follow-up is cleared.
    assert row.dynamic_followup is None
    # Now part3_index should have advanced to 1 (Bank Q1).
    assert row.part3_index == 1
    # Bank Q1 was NOT skipped!
    assert prompt2.question == "Bank Q1: Public transport"


@pytest.mark.asyncio
async def test_generate_followup_timeout_configured_to_6s():
    """Verify that _generate_followup uses a 6-second timeout."""
    mock_db = mock.MagicMock()
    conductor = IELTSSessionConductor(db=mock_db, llm_client=FakeLLMClient())

    async def fake_wait_for(coro, timeout):
        await coro
        return "Followup"

    with mock.patch("asyncio.wait_for", side_effect=fake_wait_for) as mock_wait_for:
        result = await conductor._generate_followup("Some answer", 3, "technology")
        assert result == "Followup"
        assert mock_wait_for.call_args[1]["timeout"] == 6.0
