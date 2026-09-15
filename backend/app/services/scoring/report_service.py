"""
ReportService — the orchestration layer the router talks to. Handles
report caching (so fusion + any LLM calls only run once per session),
and wires the fusion engine into history/trends/coverage/readiness/replay/
model-answer, matching the pattern of Phase 7's `IELTSSessionConductor`.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from app.models.ielts import IELTSSession
from app.models.scoring import SessionReportCache
from app.schemas.scoring import ReplayDataOut, ReplayEventOut, TrendDataOut, TrendPointOut
from app.services.scoring.coverage import CoverageMatrix, CoverageMatrixBuilder
from app.services.scoring.fusion import (
    FusedReport,
    IELTSScoreSourceAdapter,
    InterviewScoreSourceAdapter,
    QuestionBreakdown,
    ScoreFusionEngine,
)
from app.services.scoring.readiness import ReadinessAssessor, ReadinessVerdict, SessionPoint


class ReportNotFoundError(Exception):
    pass


class ReportService:
    def __init__(self, db: DBSession, fusion_engine: Optional[ScoreFusionEngine] = None):
        self.db = db
        self.fusion_engine = fusion_engine or ScoreFusionEngine(
            interview_adapter=InterviewScoreSourceAdapter(db),
            ielts_adapter=IELTSScoreSourceAdapter(db),
        )

    # -- mode detection ----------------------------------------------------

    def _detect_mode(self, session_id: str) -> str:
        from app.models.session import Session as SessionRecord

        try:
            session_row = (
                self.db.query(SessionRecord).filter(SessionRecord.id == session_id).one_or_none()
            )
            if session_row and session_row.mode:
                return session_row.mode
        except Exception:
            pass

        try:
            ielts_row = (
                self.db.query(IELTSSession.id).filter(IELTSSession.session_id == session_id).one_or_none()
            )
            return "ielts" if ielts_row is not None else "interview"
        except Exception:
            return "interview"

    # -- report (cached) -----------------------------------------------------

    async def get_report(self, session_id: str, force_refresh: bool = False) -> FusedReport:
        cached = self._get_cache_row(session_id)
        if cached and not force_refresh:
            return self._report_from_cache(cached)

        mode = self._detect_mode(session_id)
        if mode == "ielts":
            report = await self.fusion_engine.fuse_ielts_scores(session_id)
        else:
            report = await self.fusion_engine.fuse_interview_scores(session_id)

        self._save_cache(report)
        return report

    def _get_cache_row(self, session_id: str) -> Optional[SessionReportCache]:
        return (
            self.db.query(SessionReportCache)
            .filter(SessionReportCache.session_id == session_id)
            .one_or_none()
        )

    def _report_from_cache(self, row: SessionReportCache) -> FusedReport:
        data = dict(row.report_json)
        data["generated_at"] = datetime.fromisoformat(data["generated_at"])
        # Reconstruct nested dataclasses explicitly (asdict() flattened them to
        # plain dicts) — see Phase 7's `IELTSBandScore.from_dict` for the same
        # pattern and why a bare `FusedReport(**data)` isn't sufficient here.
        from app.services.scoring.fusion import (
            ActionItem,
            AnnotatedAnswer,
            CostEstimate,
            FrameworkAnalysis,
            ScoreDimension,
            SentenceAnnotation,
            SubScore,
        )

        data["dimensions"] = [
            ScoreDimension(**{**d, "sub_scores": [SubScore(**s) for s in d.get("sub_scores", [])]})
            for d in data["dimensions"]
        ]
        data["action_items"] = [ActionItem(**a) for a in data["action_items"]]

        breakdown = []
        for qb in data["per_question_breakdown"]:
            qb = dict(qb)
            if qb.get("annotated_answer"):
                aa = dict(qb["annotated_answer"])
                aa["sentences"] = [SentenceAnnotation(**s) for s in aa["sentences"]]
                aa["framework_analysis"] = FrameworkAnalysis(**aa["framework_analysis"])
                qb["annotated_answer"] = AnnotatedAnswer(**aa)
            breakdown.append(QuestionBreakdown(**qb))
        data["per_question_breakdown"] = breakdown

        if data.get("cost_estimate"):
            data["cost_estimate"] = CostEstimate(**data["cost_estimate"])

        return FusedReport(**data)

    def _save_cache(self, report: FusedReport) -> None:
        payload = asdict(report)
        payload["generated_at"] = report.generated_at.isoformat()

        row = self._get_cache_row(report.session_id)
        if row is None:
            row = SessionReportCache(session_id=report.session_id)
            self.db.add(row)

        row.mode = report.mode
        row.overall_score = report.overall_score
        row.duration_minutes = report.duration_minutes
        row.persona_label = report.persona_label
        row.jd_title = report.jd_title
        row.report_json = payload
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    # -- history / trends ----------------------------------------------------

    async def sync_history(self) -> None:
        """
        Backfills and refreshes report cache for sessions with evaluated answers
        or completed status that are missing from cache or have obsolete placeholder 0s.
        """
        try:
            from app.models.interview import QuestionTurn
            from app.models.ielts import IELTSSession

            # Find all interview session IDs with evaluated turns
            interview_sids = [
                r[0]
                for r in (
                    self.db.query(QuestionTurn.session_id)
                    .filter(QuestionTurn.answer_text.isnot(None))
                    .distinct()
                    .all()
                )
            ]
            ielts_sids = [
                r[0]
                for r in (
                    self.db.query(IELTSSession.session_id)
                    .filter(IELTSSession.status == "completed")
                    .distinct()
                    .all()
                )
            ]

            all_sids = set(interview_sids + ielts_sids)
            if not all_sids:
                return

            cached_rows = {
                r.session_id: r
                for r in self.db.query(SessionReportCache)
                .filter(SessionReportCache.session_id.in_(all_sids))
                .all()
            }

            for sid in all_sids:
                cached = cached_rows.get(sid)
                if cached is None or (cached.overall_score == 0.0 and sid in interview_sids):
                    try:
                        await self.get_report(sid, force_refresh=True)
                    except Exception as exc:
                        import logging
                        logging.getLogger("poise.scoring").debug("Could not auto-sync session %s: %s", sid, exc)
        except Exception as exc:
            import logging
            logging.getLogger("poise.scoring").warning("Failed to sync history: %s", exc)

    def list_history(self, mode: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[SessionReportCache]:
        q = self.db.query(SessionReportCache).order_by(SessionReportCache.generated_at.desc())
        if mode:
            q = q.filter(SessionReportCache.mode == mode)
        return q.offset(offset).limit(limit).all()

    def get_trends(self, mode: Optional[str] = None, last_n: int = 20) -> TrendDataOut:
        rows = self.list_history(mode=mode, limit=last_n)
        rows = list(reversed(rows))  # chronological order

        points: list[TrendPointOut] = []
        dim_totals: dict[str, list[float]] = {}
        for row in rows:
            dims = row.report_json.get("dimensions", [])
            dim_scores = {d["name"]: d["score"] for d in dims if d.get("available", True)}
            for name, score in dim_scores.items():
                dim_totals.setdefault(name, []).append(score)
            points.append(
                TrendPointOut(
                    session_id=row.session_id, generated_at=row.generated_at,
                    overall_score=row.overall_score, dimension_scores=dim_scores,
                )
            )

        dimension_averages = {
            name: round(sum(vals) / len(vals), 1) for name, vals in dim_totals.items() if vals
        }

        overall_trend = "stable"
        if len(points) >= 3:
            scores = [p.overall_score for p in points]
            mid = len(scores) // 2
            delta = (sum(scores[mid:]) / len(scores[mid:])) - (sum(scores[:mid]) / len(scores[:mid]))
            overall_trend = "improving" if delta >= 4 else "declining" if delta <= -4 else "stable"

        return TrendDataOut(points=points, dimension_averages=dimension_averages, overall_trend=overall_trend)

    # -- readiness -------------------------------------------------------------

    async def get_readiness(self, mode: Optional[str] = None, target_score: float = 75.0) -> ReadinessVerdict:
        rows = self.list_history(mode=mode, limit=50)
        rows = list(reversed(rows))
        history = [
            SessionPoint(session_id=r.session_id, overall_score=r.overall_score, generated_at=r.generated_at.isoformat())
            for r in rows
        ]
        return await ReadinessAssessor().assess(history, target_score=target_score)

    # -- coverage --------------------------------------------------------------

    async def get_coverage(self, session_id: str, jd_text: str) -> CoverageMatrix:
        report = await self.get_report(session_id)
        return await CoverageMatrixBuilder().build(jd_text, report.per_question_breakdown)

    # -- replay ------------------------------------------------------------------

    async def get_replay(self, session_id: str) -> ReplayDataOut:
        """
        Best-effort timeline reconstruction from the question breakdown.
        Real per-second playback (audio/video scrubbing, live confidence
        overlay) needs raw session telemetry from Phases 3/5, which this
        deliverable doesn't have access to — see README "Wiring the
        adapters" for where to plug that in once available.
        """
        report = await self.get_report(session_id)
        events: list[ReplayEventOut] = []
        cursor = 0.0
        per_question_s = (report.duration_minutes * 60) / max(1, len(report.per_question_breakdown))
        for qb in report.per_question_breakdown:
            events.append(ReplayEventOut(timestamp_s=round(cursor, 1), kind="question", label=qb.question))
            cursor += per_question_s * 0.15
            events.append(
                ReplayEventOut(
                    timestamp_s=round(cursor, 1), kind="answer", label=f"Score: {qb.score:.0f}/100",
                    detail=qb.user_answer[:200],
                )
            )
            cursor += per_question_s * 0.85

        return ReplayDataOut(session_id=session_id, duration_minutes=report.duration_minutes, events=events)

    # -- model answer -----------------------------------------------------------

    async def get_model_answer(self, session_id: str, question_index: int, jd_summary: str = "", resume_summary: str = ""):
        from app.services.scoring.model_answer import ModelAnswerGenerator

        report = await self.get_report(session_id)
        if question_index < 0 or question_index >= len(report.per_question_breakdown):
            raise IndexError(f"question_index {question_index} out of range for session {session_id}")

        qb = report.per_question_breakdown[question_index]
        generator = ModelAnswerGenerator()
        model_answer = await generator.generate(qb.question, jd_summary, resume_summary)
        diff = generator.diff(qb.user_answer, model_answer.full_text)
        return model_answer, diff
