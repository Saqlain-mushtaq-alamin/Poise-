"""
SQLAlchemy models for Phase 8.

`SessionReportCache` stores the computed `FusedReport` per session so
History/Analytics/PDF-export don't recompute fusion (and re-hit
Phase 4/5/6/7 data + any LLM calls) on every view. `report_json` is the
full `dataclasses.asdict(FusedReport)`; the flat columns alongside it
(`overall_score`, `mode`, `duration_minutes`) exist purely so History/
Trends can query and sort without deserializing JSON for every row.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SessionReportCache(Base):
    __tablename__ = "session_report_cache"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)

    mode = Column(String, nullable=False)             # "interview" | "ielts"
    overall_score = Column(Float, nullable=False)
    duration_minutes = Column(Float, default=0.0)
    persona_label = Column(String, nullable=True)
    jd_title = Column(String, nullable=True)

    report_json = Column(JSON, nullable=False)          # full serialized FusedReport

    generated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    debrief_messages = relationship(
        "DebriefMessage",
        primaryjoin="foreign(DebriefMessage.session_id) == SessionReportCache.session_id",
        viewonly=True,
    )


class DebriefMessage(Base):
    __tablename__ = "debrief_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)

    role = Column(String, nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
