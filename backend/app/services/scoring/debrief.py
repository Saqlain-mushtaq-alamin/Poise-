"""
Debrief chat (spec §8.4) — a short conversational coaching session
grounded in the candidate's own `FusedReport`, persisted so the
conversation survives a page refresh.
"""

from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from app.models.scoring import DebriefMessage
from app.services.scoring.fusion import FusedReport
from app.services.scoring.llm_client import ScoringLLMClient


def _summarize_report(report: FusedReport) -> str:
    dim_lines = [
        f"- {d.name}: {d.score:.0f}/100" if d.available else f"- {d.name}: not available"
        for d in report.dimensions
    ]
    lines = [
        f"Overall score: {report.overall_score:.0f}/100 ({report.mode} mode)",
        *dim_lines,
        f"Strengths: {'; '.join(report.strengths) or 'none flagged'}",
        f"Improvements: {'; '.join(report.improvements) or 'none flagged'}",
    ]
    return "\n".join(lines)


class DebriefService:
    def __init__(self, db: DBSession, llm_client: ScoringLLMClient | None = None):
        self.db = db
        self.llm_client = llm_client or ScoringLLMClient()

    def _history(self, session_id: str) -> list[DebriefMessage]:
        return (
            self.db.query(DebriefMessage)
            .filter(DebriefMessage.session_id == session_id)
            .order_by(DebriefMessage.created_at)
            .all()
        )

    async def start_or_continue(self, session_id: str, report: FusedReport) -> DebriefMessage:
        """Returns the opening coach message, generating it once and
        persisting it if this is the first call for this session."""
        existing = self._history(session_id)
        if existing:
            return existing[0]

        summary = _summarize_report(report)
        opening = await self.llm_client.debrief_opening(summary) or self._heuristic_opening(report)

        msg = DebriefMessage(session_id=session_id, role="assistant", content=opening)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    async def reply(self, session_id: str, report: FusedReport, user_message: str) -> DebriefMessage:
        history = self._history(session_id)
        history_dicts = [{"role": m.role, "content": m.content} for m in history]

        user_msg = DebriefMessage(session_id=session_id, role="user", content=user_message)
        self.db.add(user_msg)

        summary = _summarize_report(report)
        reply_text = await self.llm_client.debrief_reply(summary, history_dicts, user_message)
        if not reply_text:
            reply_text = self._heuristic_reply(report, user_message)

        assistant_msg = DebriefMessage(session_id=session_id, role="assistant", content=reply_text)
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)
        return assistant_msg

    def get_history(self, session_id: str) -> list[DebriefMessage]:
        return self._history(session_id)

    # -- heuristic fallback (no LLM configured) ---------------------------------

    def _heuristic_opening(self, report: FusedReport) -> str:
        available = [d for d in report.dimensions if d.available]
        if not available:
            return (
                f"Your overall score was {report.overall_score:.0f}/100. "
                "What would you like to talk through first?"
            )
        weakest = min(available, key=lambda d: d.score)
        strongest = max(available, key=lambda d: d.score)
        return (
            f"Let's look at your session. {strongest.name} was your strongest area at "
            f"{strongest.score:.0f}/100, while {weakest.name} came in lowest at "
            f"{weakest.score:.0f}/100. Want to start there?"
        )

    def _heuristic_reply(self, report: FusedReport, user_message: str) -> str:
        if report.improvements:
            return (
                "Connect an LLM provider (Settings > BYOK) for a fully conversational debrief. "
                f"In the meantime, here's what your report flagged: {report.improvements[0]}"
            )
        return (
            "Connect an LLM provider (Settings > BYOK) for a fully conversational debrief. "
            "Your report didn't flag any major concerns — nice work."
        )
