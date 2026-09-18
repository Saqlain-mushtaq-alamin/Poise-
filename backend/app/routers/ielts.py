"""
FastAPI router for IELTS Speaking sessions.

Registered in `app/main.py` alongside the other Phase routers:

    from app.routers import ielts
    app.include_router(ielts.router)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.ielts import IELTSAnswer
from app.schemas.ielts import (
    AnswerResultOut,
    CreateIELTSSessionRequest,
    CueCardOut,
    IELTSBandScoreOut,
    IELTSSessionDetailOut,
    IELTSSessionOut,
    PronunciationAnalysisOut,
    ProsodyAnalysisOut,
    SubmitAnswerRequest,
)
from app.services.ielts.conductor import IELTSSessionConductor, IELTSSessionNotFound

router = APIRouter(prefix="/ielts", tags=["ielts"])


def get_conductor(db: DBSession = Depends(get_db)) -> IELTSSessionConductor:
    return IELTSSessionConductor(db=db)


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"IELTS session {session_id} not found")


@router.post("/sessions", response_model=IELTSSessionOut)
async def create_session(
    body: CreateIELTSSessionRequest,
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    row = await conductor.create_session(
        target_band=body.target_band, topics_preference=body.topics_preference
    )
    return row


@router.get("/sessions/{session_id}", response_model=IELTSSessionDetailOut)
async def get_session(
    session_id: str,
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    try:
        row = conductor._get(session_id)
    except IELTSSessionNotFound:
        raise _not_found(session_id)

    prompt = conductor._current_prompt(row)
    cue_card = None
    if row.part2_cue_card:
        cue_card = CueCardOut(**row.part2_cue_card)

    return IELTSSessionDetailOut(
        **IELTSSessionOut.model_validate(row).model_dump(),
        current_prompt=prompt,
        part1_categories=row.part1_categories,
        part2_cue_card=cue_card,
        part3_questions=row.part3_questions,
    )


@router.post("/sessions/{session_id}/start", response_model=IELTSSessionDetailOut)
async def start_session(
    session_id: str,
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    try:
        prompt = await conductor.start_session(session_id)
    except IELTSSessionNotFound:
        raise _not_found(session_id)

    row = conductor._get(session_id)
    return IELTSSessionDetailOut(
        **IELTSSessionOut.model_validate(row).model_dump(), current_prompt=prompt
    )


@router.post("/sessions/{session_id}/advance", response_model=IELTSSessionDetailOut)
async def advance_session(
    session_id: str,
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    """Non-spoken transitions: intro finished, cue card acknowledged, prep timer elapsed."""
    try:
        prompt = await conductor.advance(session_id)
    except IELTSSessionNotFound:
        raise _not_found(session_id)

    row = conductor._get(session_id)
    return IELTSSessionDetailOut(
        **IELTSSessionOut.model_validate(row).model_dump(), current_prompt=prompt
    )


@router.post("/sessions/{session_id}/answer", response_model=AnswerResultOut)
async def submit_answer(
    session_id: str,
    body: SubmitAnswerRequest,
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    try:
        answer, next_prompt = await conductor.submit_answer(
            session_id, audio_path=body.audio_path, transcript=body.transcript
        )
    except IELTSSessionNotFound:
        raise _not_found(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Once we've reached SCORING, finalize immediately so the score
    # endpoint has data as soon as the client polls it.
    if next_prompt.state == "scoring":
        await conductor.finalize_score(session_id)

    return AnswerResultOut(answer_id=answer.id, next_prompt=next_prompt)


@router.get("/sessions/{session_id}/score", response_model=IELTSBandScoreOut)
async def get_score(
    session_id: str,
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    try:
        row = conductor._get(session_id)
    except IELTSSessionNotFound:
        raise _not_found(session_id)

    if not row.overall_band_score:
        raise HTTPException(status_code=409, detail="Session has not been scored yet")
    return row.overall_band_score


@router.get("/sessions/{session_id}/pronunciation", response_model=list[PronunciationAnalysisOut])
async def get_pronunciation(
    session_id: str,
    db: DBSession = Depends(get_db),
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    try:
        row = conductor._get(session_id)
    except IELTSSessionNotFound:
        raise _not_found(session_id)

    answers = (
        db.query(IELTSAnswer)
        .filter(IELTSAnswer.ielts_session_id == row.id, IELTSAnswer.pronunciation.isnot(None))
        .order_by(IELTSAnswer.created_at)
        .all()
    )
    return [a.pronunciation for a in answers]


@router.get("/sessions/{session_id}/prosody", response_model=list[ProsodyAnalysisOut])
async def get_prosody(
    session_id: str,
    db: DBSession = Depends(get_db),
    conductor: IELTSSessionConductor = Depends(get_conductor),
):
    try:
        row = conductor._get(session_id)
    except IELTSSessionNotFound:
        raise _not_found(session_id)

    answers = (
        db.query(IELTSAnswer)
        .filter(IELTSAnswer.ielts_session_id == row.id, IELTSAnswer.prosody.isnot(None))
        .order_by(IELTSAnswer.created_at)
        .all()
    )
    return [a.prosody for a in answers]
