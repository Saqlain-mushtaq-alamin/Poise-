"""10.12 — Confidence calibration: self-rating vs actual score.

Self-ratings come in on a 1-10 scale (see ReflectionEntry.self_rating);
actual scores come in on a 0-100 scale (FusedReport.overall_score). Both
are compared on the 1-10 scale (actual_score / 10) so the gap is
intuitive: "you rated yourself a 6, you actually scored an 8".
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import CalibrationRecord
from app.schemas.motivation import ConfidenceCalibration

WELL_CALIBRATED_THRESHOLD = 1.0  # +/- 1 point on the 1-10 scale


class CalibrationTracker:
    def __init__(self, db: DBSession):
        self.db = db

    def record(self, session_id: str, self_rating: float, actual_score_0_100: float) -> ConfidenceCalibration:
        existing = self.db.execute(
            select(CalibrationRecord).where(CalibrationRecord.session_id == session_id)
        ).scalars().first()
        if existing is None:
            existing = CalibrationRecord(session_id=session_id, self_rating=self_rating, actual_score=actual_score_0_100)
            self.db.add(existing)
        else:
            existing.self_rating = self_rating
            existing.actual_score = actual_score_0_100
        self.db.commit()
        return self.get_calibration()

    def get_calibration(self, window: int = 10) -> ConfidenceCalibration:
        rows = self.db.execute(
            select(CalibrationRecord).order_by(CalibrationRecord.created_at.desc()).limit(window)
        ).scalars().all()

        if not rows:
            return ConfidenceCalibration(
                self_rating=0, actual_score=0, calibration_gap=0,
                calibration_trend="well_calibrated", historical_gaps=[],
                insight="Not enough data yet — rate yourself after your next few sessions to see your calibration.",
            )

        gaps = [r.self_rating - (r.actual_score / 10.0) for r in reversed(rows)]  # chronological
        latest = rows[0]
        latest_gap = latest.self_rating - (latest.actual_score / 10.0)
        avg_gap = sum(gaps) / len(gaps)

        if avg_gap > WELL_CALIBRATED_THRESHOLD:
            trend = "over_confident"
        elif avg_gap < -WELL_CALIBRATED_THRESHOLD:
            trend = "under_confident"
        else:
            trend = "well_calibrated"

        insight = self._build_insight(trend, avg_gap, len(rows))

        return ConfidenceCalibration(
            self_rating=latest.self_rating,
            actual_score=latest.actual_score,
            calibration_gap=round(latest_gap, 2),
            calibration_trend=trend,
            historical_gaps=[round(g, 2) for g in gaps],
            insight=insight,
        )

    @staticmethod
    def _build_insight(trend: str, avg_gap: float, n: int) -> str:
        magnitude = abs(round(avg_gap, 1))
        if trend == "under_confident":
            return (
                f"Across your last {n} sessions, you rated yourself about {magnitude} points lower "
                f"than your actual performance, on average. You're better than you think!"
            )
        if trend == "over_confident":
            return (
                f"Across your last {n} sessions, you rated yourself about {magnitude} points higher "
                f"than your actual performance, on average. Worth a closer look at where the gap comes from."
            )
        return f"Your self-ratings have tracked closely with your actual scores over your last {n} sessions — solid self-awareness."
