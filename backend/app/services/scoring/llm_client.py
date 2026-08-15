"""
Thin wrapper around Phase 2's BYOK model router, shared by every Phase 8
service that wants LLM assistance (debrief chat, model answers, richer
sentence annotation). Same pattern as Phase 7's `IELTSLLMClient` — every
method returns `None` when no provider is configured, and every caller in
this phase has a heuristic fallback so a report/debrief/model-answer never
hard-fails just because Cloud Assist isn't set up.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Optional

from app.services.json_utils import extract_json_from_llm

logger = logging.getLogger(__name__)


class ModelRole(str, Enum):
    """
    Stand-in for Phase 2's real `ModelRole` enum (`REASONING`, `FAST`,
    `VISION`, ...) — used only for the type signature below. Replace this
    import with `from app.services.providers.router import ModelRole` once
    merged (see README "Wiring the adapters").
    """

    REASONING = "reasoning"
    FAST = "fast"


class ScoringLLMClient:
    def __init__(self, router=None, model: str = "gpt-4o-mini"):
        self.router = router
        self.model = model

    @property
    def is_configured(self) -> bool:
        return self.router is not None

    async def _complete_text(
        self, system: str, user: str, model_role: ModelRole = ModelRole.REASONING, max_tokens: int = 500
    ) -> Optional[str]:
        if not self.is_configured:
            return None
        try:
            return await self.router.complete(
                model=self.model, system=system, messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scoring LLM call failed, falling back to heuristics: %s", exc)
            return None

    async def _complete_json(self, system: str, user: str, max_tokens: int = 1200) -> Optional[dict]:
        if not self.is_configured:
            return None
        try:
            raw = await self.router.complete(
                model=self.model, system=system, messages=[{"role": "user", "content": user}],
                response_format="json", max_tokens=max_tokens,
            )
            cleaned_response = extract_json_from_llm(raw)
            return json.loads(cleaned_response)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scoring LLM JSON call failed, falling back to heuristics: %s", exc)
            return None

    # -- debrief --------------------------------------------------------------

    async def debrief_opening(self, report_summary: str) -> Optional[str]:
        return await self._complete_text(
            system=(
                "You are a warm, direct interview coach debriefing a candidate right after "
                "their practice session. Open the conversation by naming ONE specific, "
                "evidence-based observation from their report — not generic encouragement."
            ),
            user=f"Session report summary:\n{report_summary}\n\nOpen the debrief conversation.",
        )

    async def debrief_reply(self, report_summary: str, history: list[dict], user_message: str) -> Optional[str]:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[-8:])
        return await self._complete_text(
            system=(
                "You are an interview coach continuing a debrief conversation. Stay grounded "
                "in the report data provided — don't invent specifics that aren't there."
            ),
            user=f"Report summary:\n{report_summary}\n\nConversation so far:\n{transcript}\n\n"
            f"Candidate says: \"{user_message}\"\n\nReply as the coach.",
        )

    # -- sentence annotation ---------------------------------------------------

    async def annotate_sentences(self, answer: str, question: str) -> Optional[dict]:
        return await self._complete_json(
            system=(
                "You are an interview coach annotating a candidate's answer sentence by "
                "sentence. For each sentence return a rating (strong/adequate/weak/filler/"
                "off_topic), a one-line reason, and an optional suggestion."
            ),
            user=(
                f"Question: {question}\nAnswer:\n{answer}\n\n"
                'Return JSON: {"sentences": [{"text": "...", "rating": "...", "reason": "...", '
                '"suggestion": "..." or null}], "overall_structure": "well_structured|rambling|'
                'too_brief|unfocused"}'
            ),
        )

    # -- model answers ----------------------------------------------------------

    async def generate_model_answer(self, question: str, jd_summary: str, resume_summary: str) -> Optional[dict]:
        return await self._complete_json(
            system=(
                "You write strong interview answers GROUNDED IN THE CANDIDATE'S OWN "
                "BACKGROUND — never invent experience they don't have. Use their real resume "
                "details, structured optimally (usually STAR for behavioral questions)."
            ),
            user=(
                f"Question: {question}\nJob description summary: {jd_summary}\n"
                f"Candidate resume summary: {resume_summary}\n\n"
                'Return JSON: {"full_text": "...", "framework_used": "STAR", '
                '"key_elements": ["..."], "why_it_works": "..."}'
            ),
            max_tokens=700,
        )

    # -- readiness recommendation -------------------------------------------------

    async def readiness_recommendation(self, evidence_summary: str) -> Optional[str]:
        return await self._complete_text(
            system="You give one concise, specific, prioritized recommendation sentence.",
            user=f"Evidence:\n{evidence_summary}\n\nWhat should this candidate focus on next?",
            max_tokens=120,
        )
