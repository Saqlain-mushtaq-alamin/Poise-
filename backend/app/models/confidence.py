"""Confidence frame persistence.

`session_id` is a plain string, not a foreign key to `sessions` — Phase 5
is explicitly designed to "run in complete isolation with mock session
data" (per the spec's dependency note), so this table shouldn't require a
real interview session to exist. In practice it'll usually be a real
session id from Phase 4, but nothing here enforces that.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConfidenceFrameRecord(Base):
    __tablename__ = "confidence_frames"
    __table_args__ = (Index("ix_confidence_frames_session_id", "session_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String)
    timestamp_ms: Mapped[int]
    eye_contact_json: Mapped[str] = mapped_column(String)
    head_stability_json: Mapped[str] = mapped_column(String)
    blink_json: Mapped[str] = mapped_column(String)
    gesture_json: Mapped[str | None] = mapped_column(String, nullable=True)
    expression: Mapped[str] = mapped_column(String)
    composite_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
