"""
Integration adapter between the Motivation Engine and the rest of the
codebase.

The master plan has every phase talk through *contracts*, not concrete
tables — Phase 10 was written against `FusedReport` / `AnswerEvaluation` /
`ConfidenceSummary` etc. as **dataclasses returned by service calls**, not
as fixed ORM tables. Your Phase 8 implementation is the source of truth
for how those actually get persisted, and I don't have that code here —
so this module is the *one* place Phase 10 reaches into "the rest of the
app". Every other motivation service imports from here, never from
`app.models.report` or similar directly.

Wire the four functions below to your real Phase 8 persistence layer and
the rest of Phase 10 works unmodified. Reasonable defaults / soft-fails
are provided so the module still imports and runs (with empty data)
before you've wired it up.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session as DBSession


@dataclass
class ScorePoint:
    session_id: str
    session_date: date
    mode: str  # "interview" | "ielts"
    overall_score: float  # 0-100 for interview, IELTS band * 12.5 (i.e. band 8 == 100) for ielts
    ielts_band: float | None
    duration_minutes: float
    weakest_dimension: str | None
    weakest_dimension_score: float | None


@dataclass
class SessionWeaknesses:
    """Everything Phase 10.3 needs to mint/update spaced-repetition items."""
    behavioral: list[str]       # from AnswerEvaluation.improvements
    technical: list[str]        # from CodeEvaluation.improvements
    pronunciation: list[str]    # from PronunciationAnalysis.problem_sounds
    topics: list[str]           # from FusedReport.action_items / ConfidenceSummary.notable_moments


def get_recent_score_points(db: DBSession, mode: str | None = None, limit: int = 200) -> list[ScorePoint]:
    """Return recent fused-report scores, most recent first.

    TODO(wire-me): replace with a real query against your Phase 8 report
    table, e.g.:

        from app.models.report import SessionReport
        q = db.query(SessionReport)
        if mode:
            q = q.filter(SessionReport.mode == mode)
        rows = q.order_by(SessionReport.generated_at.desc()).limit(limit).all()
        return [ScorePoint(
            session_id=r.session_id, session_date=r.generated_at.date(),
            mode=r.mode, overall_score=r.overall_score,
            ielts_band=r.ielts_band, duration_minutes=r.duration_minutes,
            weakest_dimension=r.weakest_dimension, weakest_dimension_score=r.weakest_dimension_score,
        ) for r in rows]
    """
    try:
        from app.models.report import SessionReport  # type: ignore
    except ImportError:
        return []

    q = db.query(SessionReport)
    if mode:
        q = q.filter(SessionReport.mode == mode)
    rows = q.order_by(SessionReport.generated_at.desc()).limit(limit).all()
    return [
        ScorePoint(
            session_id=r.session_id,
            session_date=(r.generated_at.date() if isinstance(r.generated_at, datetime) else r.generated_at),
            mode=r.mode,
            overall_score=r.overall_score,
            ielts_band=getattr(r, "ielts_band", None),
            duration_minutes=getattr(r, "duration_minutes", 0.0) or 0.0,
            weakest_dimension=getattr(r, "weakest_dimension", None),
            weakest_dimension_score=getattr(r, "weakest_dimension_score", None),
        )
        for r in rows
    ]


def get_session_weaknesses(db: DBSession, session_id: str) -> SessionWeaknesses:
    """TODO(wire-me): pull the real lists off your stored FusedReport /
    AnswerEvaluation / CodeEvaluation / PronunciationAnalysis rows for
    this session_id. Returning empty lists is a safe no-op default."""
    try:
        import json

        from app.models.report import SessionReport  # type: ignore

        r = db.query(SessionReport).filter(SessionReport.session_id == session_id).first()
        if not r:
            return SessionWeaknesses([], [], [], [])
        return SessionWeaknesses(
            behavioral=json.loads(getattr(r, "behavioral_improvements", "[]") or "[]"),
            technical=json.loads(getattr(r, "technical_improvements", "[]") or "[]"),
            pronunciation=json.loads(getattr(r, "problem_sounds", "[]") or "[]"),
            topics=json.loads(getattr(r, "action_item_topics", "[]") or "[]"),
        )
    except ImportError:
        return SessionWeaknesses([], [], [], [])


def get_session_duration_minutes(db: DBSession, session_id: str) -> float:
    try:
        from app.models.session import Session as SessionModel  # type: ignore

        s = db.get(SessionModel, session_id)
        if s is None:
            return 0.0
        # TODO(wire-me): adjust to your real duration field/computation
        started = getattr(s, "created_at", None)
        ended = getattr(s, "updated_at", None)
        if started and ended:
            return max(0.0, (ended - started).total_seconds() / 60.0)
        return 0.0
    except ImportError:
        return 0.0


def get_untested_jd_skills(db: DBSession) -> list[str]:
    """TODO(wire-me): source from Phase 8's CoverageMatrix.untested_skills
    for the user's active job description."""
    try:
        from app.models.report import CoverageMatrix  # type: ignore

        row = db.query(CoverageMatrix).order_by(CoverageMatrix.id.desc()).first()  # type: ignore[attr-defined]
        if row is None:
            return []
        import json
        return json.loads(getattr(row, "untested_skills", "[]") or "[]")
    except ImportError:
        return []
