"""
SQLAlchemy ORM models for IELTS Speaking sessions.

Follows the Phase 1 pattern (`app.database.Base`, UUID string PKs,
`sessions` table already defined in Phase 1's `models/session.py` with
`mode = \"ielts\"`). This module adds the IELTS-specific detail tables that
hang off that shared `sessions` row via `session_id`.
"""

from __future__ import annotations

from datetime import datetime, timezone
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


def _now():
    return datetime.now(timezone.utc)


class IELTSSession(Base):
    __tablename__ = "ielts_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)

    status = Column(String, nullable=False, default="setup")
    target_band = Column(Float, nullable=False, default=6.5)
    topics_preference = Column(String, nullable=True)

    part1_categories = Column(JSON, nullable=True)   # list[dict] from topics.py
    part1_index = Column(Integer, default=0)          # which category we're on
    part1_question_index = Column(Integer, default=0)

    part2_cue_card = Column(JSON, nullable=True)
    part2_followup_asked = Column(Integer, default=0)  # 0/1 boolean flag
    # Transcript of the Part 2 long-turn answer — used to generate a
    # contextual follow-up question instead of the old hardcoded generic.
    part2_answer_transcript = Column(Text, nullable=True)

    part3_questions = Column(JSON, nullable=True)
    part3_index = Column(Integer, default=0)

    # Stores a dynamically-generated follow-up question (LLM-produced) that
    # should be asked on the next turn before the bank question.
    dynamic_followup = Column(Text, nullable=True)

    overall_band_score = Column(JSON, nullable=True)   # serialized IELTSBandScore

    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

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
    pronunciation = Column(JSON, nullable=True)        # serialized PronunciationAnalysis
    prosody = Column(JSON, nullable=True)              # serialized ProsodyAnalysis

    created_at = Column(DateTime(timezone=True), default=_now)

    ielts_session = relationship("IELTSSession", back_populates="answers")
