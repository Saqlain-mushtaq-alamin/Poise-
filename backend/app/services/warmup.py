"""Warm-up / small talk phase, per the Phase 4 spec's §4.3a.

The stage sequencing (`next_stage`, `is_warm_up_complete`) is pure,
deterministic, and fully tested without an LLM — it's just "what's the
next step in a fixed 4-step flow". Generating the actual greeting/response
text needs an LLM call (mocked in tests, same as ingestion.py/planner.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ingestion import JobDescription, ResumeData
from app.services.personas import Persona
from app.services.provider import ModelProviderRouter, ModelRole

SMALL_TALK_FLOW = ["greeting", "logistics", "ice_breaker", "role_context"]


@dataclass
class WarmUpResponse:
    text: str
    next_stage: str | None  # None means the warm-up phase is complete
    is_complete: bool


def next_stage(current_stage: str) -> str | None:
    """Returns the stage after `current_stage`, or None if `current_stage`
    was the last one in the flow."""
    try:
        idx = SMALL_TALK_FLOW.index(current_stage)
    except ValueError:
        return SMALL_TALK_FLOW[0]  # unknown/no stage yet -> start from the top
    if idx + 1 < len(SMALL_TALK_FLOW):
        return SMALL_TALK_FLOW[idx + 1]
    return None


def is_warm_up_complete(current_stage: str) -> bool:
    return next_stage(current_stage) is None


GREETING_PROMPT_TEMPLATE = """You are {persona_name}. {persona_style}

Generate a warm, brief opening greeting (2-3 sentences) for the very start of an \
interview with {candidate_name} for the {role_title} role{company_clause}. If there's a \
low-stakes, specific detail from their background below (a location, a notable project), \
you may reference it briefly to sound natural rather than generic — but don't force it. \
Do not ask any question related to the actual interview content yet; this is purely the \
opening hello.

Candidate background:
{resume_summary}"""

SMALL_TALK_RESPONSE_PROMPT_TEMPLATE = """You are {persona_name}. {persona_style}

You're in the small-talk warm-up phase of an interview, at the "{stage}" step. The \
candidate just said: "{user_response}"

Respond naturally and briefly (1-2 sentences), staying in the spirit of casual pre-interview \
conversation. {stage_guidance}"""

_STAGE_GUIDANCE = {
    "greeting": "Acknowledge their reply, then briefly explain how the interview will go "
    "(logistics) — roughly how long, what format.",
    "logistics": "Ask a light, low-stakes ice-breaker question unrelated to the role itself.",
    "ice_breaker": "Transition into asking what attracted them to this specific role, "
    "briefly and warmly.",
    "role_context": "Acknowledge their answer and let them know you're moving into the "
    "first real question now.",
}


class WarmUpConductor:
    def __init__(self, provider: ModelProviderRouter) -> None:
        self.provider = provider

    async def generate_greeting(
        self, persona: Persona, resume: ResumeData, jd: JobDescription
    ) -> str:
        company_clause = f" at {jd.company}" if jd.company else ""
        prompt = GREETING_PROMPT_TEMPLATE.format(
            persona_name=persona.name,
            persona_style=persona.style,
            candidate_name=resume.name or "the candidate",
            role_title=jd.title,
            company_clause=company_clause,
            resume_summary=resume.summary or "(no summary available)",
        )
        try:
            return await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model_role=ModelRole.REASONING,
                stream=False,
            )
        except Exception:
            return f"Hello {resume.name or 'there'}! Welcome to your interview for the {jd.title} position. It's great to connect with you today."

    async def respond_to_small_talk(
        self, user_response: str, current_stage: str, persona: Persona
    ) -> WarmUpResponse:
        stage_guidance = _STAGE_GUIDANCE.get(current_stage, "Keep the conversation moving.")
        prompt = SMALL_TALK_RESPONSE_PROMPT_TEMPLATE.format(
            persona_name=persona.name,
            persona_style=persona.style,
            stage=current_stage,
            user_response=user_response,
            stage_guidance=stage_guidance,
        )
        try:
            text = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model_role=ModelRole.REASONING,
                stream=False,
            )
        except Exception:
            text = "Thank you for sharing that! Let's get started with our interview."

        upcoming = next_stage(current_stage)
        return WarmUpResponse(text=text, next_stage=upcoming, is_complete=upcoming is None)
