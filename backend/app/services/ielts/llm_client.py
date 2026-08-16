"""
Thin wrapper around the BYOK model router (Phase 2's `litellm`-based
provider layer). IELTS services depend only on this interface, never on
`litellm` directly, so Phase 2's actual router can be swapped in without
touching scorer/topics/prosody code.

If no provider is configured (no key set, or Phase 2 router unavailable),
every method returns `None` and callers fall back to heuristic/offline
behaviour — the app must never hard-fail an IELTS session just because
Cloud Assist isn't configured.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """You are an experienced, calibrated IELTS Speaking examiner.
You score strictly against the official IELTS Speaking band descriptors (0-9, 0.5
increments). Be discriminating: a genuinely weak response must score lower than a
strong one. Always ground your justification in specific evidence from the
transcript, and always return valid JSON matching the requested schema exactly."""


class IELTSLLMClient:
    """
    Optional dependency injection point. In production this is constructed
    with a reference to Phase 2's `ModelRouter` (BYOK-aware, tier-aware).
    Here it degrades gracefully so this phase can be developed and tested
    in isolation, per the master plan's phase-independence strategy.
    """

    def __init__(self, router=None, model: str = "gpt-4o-mini"):
        self.router = router
        self.model = model

    @property
    def is_configured(self) -> bool:
        return self.router is not None

    async def _complete_json(self, system: str, user: str) -> Optional[dict]:
        if not self.is_configured:
            return None
        try:
            raw = await self.router.complete(
                model=self.model,
                system=system,
                messages=[{"role": "user", "content": user}],
                response_format="json",
                max_tokens=1200,
            )
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - never let scoring crash a session
            logger.warning("IELTS LLM call failed, falling back to heuristics: %s", exc)
            return None

    async def _complete_text(self, system: str, user: str) -> Optional[str]:
        if not self.is_configured:
            return None
        try:
            return await self.router.complete(
                model=self.model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=200,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("IELTS LLM call failed, falling back to generic prompt: %s", exc)
            return None

    async def generate_topic_variation(self, theme: str) -> Optional[str]:
        return await self._complete_text(
            system="You write a single, natural IELTS Part 3 discussion question. "
            "Reply with only the question, no preamble.",
            user=f"Theme: {theme}. Write one abstract, thought-provoking Part 3 question "
            f"on this theme that isn't a cliché.",
        )

    async def generate_followup(self, answer: str, part: int, theme: str) -> Optional[str]:
        return await self._complete_text(
            system="You are an IELTS examiner. Reply with only the follow-up question.",
            user=f"Part {part}, theme '{theme}'. Candidate answered: \"{answer}\"\n"
            f"Ask one natural, contextual follow-up question that responds to what "
            f"they actually said.",
        )

    async def score_criterion(self, criterion: str, transcript: str, context: str) -> Optional[dict]:
        """Returns dict matching BandDetail fields, or None if unavailable."""
        return await self._complete_json(
            system=SCORING_SYSTEM_PROMPT,
            user=(
                f"Criterion: {criterion}\n"
                f"Context: {context}\n"
                f"Candidate transcript:\n\"\"\"\n{transcript}\n\"\"\"\n\n"
                'Return JSON: {"band": <0-9 in 0.5 steps>, "justification": "...", '
                '"strengths": ["..."], "areas_to_improve": ["..."], '
                '"example_from_response": "short direct quote (<15 words)"}'
            ),
        )

    async def score_session_criterion(self, criterion: str, full_transcript: str) -> Optional[dict]:
        """Holistic evaluation across the entire session transcript."""
        return await self._complete_json(
            system=SCORING_SYSTEM_PROMPT,
            user=(
                f"Criterion: {criterion}\n"
                f"Evaluate the candidate holistically based on this entire IELTS speaking session transcript:\n\"\"\"\n{full_transcript}\n\"\"\"\n\n"
                'Return JSON: {"band": <0-9 in 0.5 steps>, "justification": "...", '
                '"strengths": ["..."], "areas_to_improve": ["..."], '
                '"example_from_response": "short direct quote (<15 words)"}'
            ),
        )
