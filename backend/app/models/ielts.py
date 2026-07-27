"""
SQLAlchemy ORM models for IELTS Speaking sessions.

Follows the Phase 1 pattern (`app.database.Base`, UUID string PKs,
`sessions` table already defined in Phase 1's `models/session.py` with
`mode = "ielts"`). This module adds the IELTS-specific detail tables that
hang off that shared `sessions` row via `session_id`.

Alembic migration stub: see `alembic/versions/` — add a revision that
creates `ielts_sessions` and `ielts_answers` per the schema below.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class IELTSSession(Base):
    __tablename__ = "ielts_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)

    status = Column(String, nullable=False, default="setup")
    target_band = Column(Float, nullable=False, default=6.5)
    topics_preference = Column(String, nullable=True)

    part1_categories = Column(JSON, nullable=True)   # list[dict] from topics.py
    part1_index = Column(Integer, default=0)          # which category/question we're on
    part1_question_index = Column(Integer, default=0)

    part2_cue_card = Column(JSON, nullable=True)
    part2_followup_asked = Column(Integer, default=0)  # 0/1 boolean flag

    part3_questions = Column(JSON, nullable=True)
    part3_index = Column(Integer, default=0)

    overall_band_score = Column(JSON, nullable=True)   # serialized IELTSBandScore

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    answers = relationship("IELTSAnswer", back_populates="ielts_session", cascade="all, delete-orphan")


class IELTSAnswer(Base):
    __tablename__ = "ielts_answers"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    ielts_session_id = Column(String, ForeignKey("ielts_sessions.id"), nullable=False)

    part = Column(Integer, nullable=False)             # 1, 2, or 3
    question_text = Column(Text, nullable=False)

    audio_path = Column(String, nullable=True)
    transcript = Column(Text, nullable=True)

    band_score = Column(JSON, nullable=True)           # serialized IELTSBandScore for this answer
    pronunciation = Column(JSON, nullable=True)         # serialized PronunciationAnalysis
    prosody = Column(JSON, nullable=True)                # serialized ProsodyAnalysis

    created_at = Column(DateTime, default=datetime.utcnow)

    ielts_session = relationship("IELTSSession", back_populates="answers")
