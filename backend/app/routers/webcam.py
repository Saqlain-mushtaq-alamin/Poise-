"""Webcam confidence endpoints, per Phase 5 spec's §"API Contracts Exposed"
(plus baseline comparison and progress, added per §5.12/§5.13).

Runs in complete isolation, as the spec requires: nothing here depends on
Phase 4's session records existing — `session_id` is just a grouping key.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.confidence import ConfidenceFrameRecord
from app.services.confidence import (
    BaselineComparison,
    ConfidenceFrame,
    ConfidenceSummary,
    ConfidenceTimeline,
    ProgressPoint,
    compute_baseline_comparison,
    compute_progress,
    compute_summary,
)

router = APIRouter(prefix="/webcam", tags=["webcam"])


def _record_to_frame(record: ConfidenceFrameRecord) -> ConfidenceFrame:
    return ConfidenceFrame(
        timestamp_ms=record.timestamp_ms,
        eye_contact=json.loads(record.eye_contact_json),
        head_stability=json.loads(record.head_stability_json),
        blink_rate=json.loads(record.blink_json),
        gesture=json.loads(record.gesture_json) if record.gesture_json else None,
        expression=record.expression,
        composite_score=record.composite_score,
    )


def _get_frames(db: DBSession, session_id: str) -> list[ConfidenceFrame]:
    records = (
        db.query(ConfidenceFrameRecord)
        .filter(ConfidenceFrameRecord.session_id == session_id)
        .order_by(ConfidenceFrameRecord.timestamp_ms)
        .all()
    )
    return [_record_to_frame(r) for r in records]


@router.post("/session/{session_id}/frames")
def submit_frames(
    session_id: str, frames: list[ConfidenceFrame], db: DBSession = Depends(get_db)
) -> dict:
    for frame in frames:
        db.add(
            ConfidenceFrameRecord(
                session_id=session_id,
                timestamp_ms=frame.timestamp_ms,
                eye_contact_json=frame.eye_contact.model_dump_json(),
                head_stability_json=frame.head_stability.model_dump_json(),
                blink_json=frame.blink_rate.model_dump_json(),
                gesture_json=frame.gesture.model_dump_json() if frame.gesture else None,
                expression=frame.expression,
                composite_score=frame.composite_score,
            )
        )
    db.commit()
    return {"session_id": session_id, "frames_stored": len(frames)}


@router.get("/session/{session_id}/timeline", response_model=ConfidenceTimeline)
def get_timeline(session_id: str, db: DBSession = Depends(get_db)) -> ConfidenceTimeline:
    frames = _get_frames(db, session_id)
    if not frames:
        raise HTTPException(
            status_code=404, detail=f"No confidence frames for session {session_id}"
        )
    return ConfidenceTimeline(session_id=session_id, frames=frames, summary=compute_summary(frames))


@router.get("/session/{session_id}/summary", response_model=ConfidenceSummary)
def get_summary(session_id: str, db: DBSession = Depends(get_db)) -> ConfidenceSummary:
    frames = _get_frames(db, session_id)
    if not frames:
        raise HTTPException(
            status_code=404, detail=f"No confidence frames for session {session_id}"
        )
    return compute_summary(frames)


@router.get("/session/{session_id}/baseline-comparison", response_model=BaselineComparison)
def get_baseline_comparison(
    session_id: str,
    warmup_end_ms: int = Query(..., description="Timestamp marking the end of the warm-up phase"),
    db: DBSession = Depends(get_db),
) -> BaselineComparison:
    frames = _get_frames(db, session_id)
    if not frames:
        raise HTTPException(
            status_code=404, detail=f"No confidence frames for session {session_id}"
        )
    warmup_frames = [f for f in frames if f.timestamp_ms < warmup_end_ms]
    interview_frames = [f for f in frames if f.timestamp_ms >= warmup_end_ms]
    return compute_baseline_comparison(warmup_frames, interview_frames)


@router.get("/progress", response_model=list[ProgressPoint])
def get_progress(
    session_ids: list[str] = Query(..., description="Session ids in chronological order"),
    db: DBSession = Depends(get_db),
) -> list[ProgressPoint]:
    summaries = []
    for session_id in session_ids:
        frames = _get_frames(db, session_id)
        summaries.append(compute_summary(frames))
    return compute_progress(session_ids, summaries)
