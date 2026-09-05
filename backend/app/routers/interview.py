"""Interview engine endpoints, per Phase 4 spec.

This is the integration point for every other Phase 4 module: ingestion,
planner, state_machine, warmup, conductor, personas, company_formats.
Where those modules each have their own focused unit tests, this router's
tests (test_interview_routes.py) exercise the full request/response
lifecycle through FastAPI's TestClient with the LLM provider mocked at the
dependency-injection boundary — the most "integration-shaped" tests in
this codebase.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.interview import InterviewSessionDetail, JobDescriptionRecord, QuestionTurn, Resume
from app.models.session import Session as SessionRecord
from app.services.company_formats import UnknownCompanyFormatError, list_company_formats
from app.services.conductor import InterviewConductor
from app.services.scoring.report_service import ReportService
from app.services.ingestion import (
    JDParser,
    JobDescription,
    ResumeData,
    ResumeParser,
    StructuringError,
    UnsupportedFileTypeError,
)
from app.services.personas import UnknownPersonaError, get_persona, list_personas
from app.services.planner import (
    InterviewConfig,
    InterviewPlan,
    InterviewPlanner,
    PlanGenerationError,
)
from app.services.provider import ModelProviderRouter, get_router
from app.services.state_machine import InvalidTransitionError, SessionStateMachine
from app.services.warmup import WarmUpConductor

router = APIRouter(prefix="/interview", tags=["interview"])


# ---- request/response models ----


class ParseJDRequest(BaseModel):
    text: str


class GeneratePlanRequest(BaseModel):
    resume_id: str
    jd_id: str
    config: InterviewConfig = InterviewConfig()


class CreateSessionRequest(BaseModel):
    resume_id: str
    jd_id: str
    config: InterviewConfig = InterviewConfig()
    persona_id: str = "professional"
    session_mode: str = "practice"  # practice | exam
    plan: InterviewPlan | None = None  # pass a pre-generated plan to skip regenerating one


class SessionResponse(BaseModel):
    session_id: str
    state: str
    persona_id: str
    session_mode: str
    plan: InterviewPlan | None = None


class WarmUpRespondRequest(BaseModel):
    text: str


class WarmUpRespondResponse(BaseModel):
    message: str
    is_complete: bool
    first_question: str | None = None
    question_id: str | None = None


class AnswerRequest(BaseModel):
    text: str


class AnswerResponse(BaseModel):
    score: float
    feedback: str
    reaction: str | None
    next_action: str  # follow_up | next_question | session_complete
    next_message: str | None = None
    next_question_id: str | None = None
    framework_missing: list[str] = []


class EvaluationRecordResponse(BaseModel):
    question_id: str
    question_text: str
    is_follow_up: bool
    answer_text: str | None
    score: float | None
    feedback: str | None


# ---- helpers ----


def _get_session_detail(db: DBSession, session_id: str) -> InterviewSessionDetail:
    detail = db.get(InterviewSessionDetail, session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No interview session with id {session_id}")
    return detail


def _load_plan(detail: InterviewSessionDetail) -> InterviewPlan | None:
    if not detail.plan_json:
        return None
    return InterviewPlan.model_validate_json(detail.plan_json)


def _current_planned_question(detail: InterviewSessionDetail):
    plan = _load_plan(detail)
    if plan is None:
        return None
    if detail.current_section_index >= len(plan.sections):
        return None
    section = plan.sections[detail.current_section_index]
    if detail.current_question_index >= len(section.questions):
        return None
    return section.questions[detail.current_question_index], section


def _advance_question_index(detail: InterviewSessionDetail) -> bool:
    """Moves to the next question in the plan. Returns False if the plan
    is exhausted (no more questions in any remaining section)."""
    plan = _load_plan(detail)
    if plan is None:
        return False

    detail.current_question_index += 1
    while detail.current_section_index < len(plan.sections):
        section = plan.sections[detail.current_section_index]
        if detail.current_question_index < len(section.questions):
            return True
        detail.current_section_index += 1
        detail.current_question_index = 0
    return False


# ---- resume / JD parsing ----


@router.post("/parse-resume")
async def parse_resume(
    file: UploadFile,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
):
    suffix = Path(file.filename or "").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        parser = ResumeParser(provider)
        try:
            data = await parser.parse(tmp_path)
        except UnsupportedFileTypeError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        except StructuringError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err
    finally:
        tmp_path.unlink(missing_ok=True)

    record = Resume(
        filename=file.filename,
        full_text=data.full_text,
        structured_json=data.model_dump_json(),
    )
    db.add(record)
    db.commit()

    return {"resume_id": record.id, "resume": json.loads(data.model_dump_json())}


@router.post("/parse-jd")
async def parse_jd(
    body: ParseJDRequest,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
):
    parser = JDParser(provider)
    try:
        data = await parser.parse(body.text)
    except StructuringError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    record = JobDescriptionRecord(raw_text=body.text, structured_json=data.model_dump_json())
    db.add(record)
    db.commit()

    return {"jd_id": record.id, "job_description": json.loads(data.model_dump_json())}


class ParseResumeTextRequest(BaseModel):
    text: str


@router.post("/parse-resume-text")
async def parse_resume_text(
    body: ParseResumeTextRequest,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
):
    """Parse a resume from raw text (no file upload). Mirrors /parse-resume
    but accepts a JSON body with {"text": "..."} for cases where the client
    has already extracted the text, or is passing clipboard content."""
    parser = ResumeParser(provider)
    try:
        data = await parser.parse_text(body.text)
    except StructuringError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    record = Resume(
        filename="text-input",
        full_text=body.text,
        structured_json=data.model_dump_json(),
    )
    db.add(record)
    db.commit()

    return {"resume_id": record.id, "resume": json.loads(data.model_dump_json())}


def _load_resume(db: DBSession, resume_id: str) -> ResumeData:
    row = db.get(Resume, resume_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No resume with id {resume_id}")
    return ResumeData.model_validate_json(row.structured_json)


def _load_jd(db: DBSession, jd_id: str) -> JobDescription:
    row = db.get(JobDescriptionRecord, jd_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No job description with id {jd_id}")
    return JobDescription.model_validate_json(row.structured_json)


@router.post("/generate-plan", response_model=InterviewPlan)
async def generate_plan(
    body: GeneratePlanRequest,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
) -> InterviewPlan:
    resume = _load_resume(db, body.resume_id)
    jd = _load_jd(db, body.jd_id)

    planner = InterviewPlanner(provider)
    try:
        return await planner.generate_plan(resume, jd, body.config)
    except PlanGenerationError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


@router.get("/personas")
def get_personas():
    return [p.__dict__ for p in list_personas()]


@router.get("/company-formats")
def get_company_formats():
    return [f.__dict__ for f in list_company_formats()]


# ---- session lifecycle ----


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    body: CreateSessionRequest,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
) -> SessionResponse:
    resume = _load_resume(db, body.resume_id)
    jd = _load_jd(db, body.jd_id)

    try:
        get_persona(body.persona_id)
    except UnknownPersonaError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    if body.config.company_format:
        try:
            from app.services.company_formats import get_company_format

            get_company_format(body.config.company_format)
        except UnknownCompanyFormatError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    plan = body.plan
    if plan is None:
        planner = InterviewPlanner(provider)
        try:
            plan = await planner.generate_plan(resume, jd, body.config)
        except PlanGenerationError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err

    session_id = str(uuid4())
    session_record = SessionRecord(id=session_id, mode="interview", status="created")
    db.add(session_record)

    sm = SessionStateMachine(session_id=session_id)
    sm.fire("start_session")
    sm.fire("upload_complete")
    sm.fire("plan_generated")

    detail = InterviewSessionDetail(
        session_id=session_id,
        resume_id=body.resume_id,
        jd_id=body.jd_id,
        config_json=body.config.model_dump_json(),
        plan_json=plan.model_dump_json(),
        persona_id=body.persona_id,
        session_mode=body.session_mode,
        company_format=body.config.company_format,
        state=sm.state,
    )
    db.add(detail)
    db.commit()

    return SessionResponse(
        session_id=session_id,
        state=detail.state,
        persona_id=detail.persona_id,
        session_mode=detail.session_mode,
        plan=plan,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: DBSession = Depends(get_db)) -> SessionResponse:
    detail = _get_session_detail(db, session_id)
    return SessionResponse(
        session_id=session_id,
        state=detail.state,
        persona_id=detail.persona_id,
        session_mode=detail.session_mode,
        plan=_load_plan(detail),
    )


@router.post("/sessions/{session_id}/start", response_model=WarmUpRespondResponse)
async def start_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
) -> WarmUpRespondResponse:
    detail = _get_session_detail(db, session_id)
    sm = SessionStateMachine(session_id=session_id, state=detail.state)

    try:
        sm.fire("begin_interview")
    except InvalidTransitionError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    resume = _load_resume(db, detail.resume_id) if detail.resume_id else ResumeData(full_text="")
    jd = _load_jd(db, detail.jd_id) if detail.jd_id else JobDescription(title="the role")
    persona = get_persona(detail.persona_id)

    conductor_warmup = WarmUpConductor(provider)
    greeting = await conductor_warmup.generate_greeting(persona, resume, jd)

    detail.state = sm.state
    detail.warm_up_stage = "greeting"
    detail.started_at = datetime.now(timezone.utc)
    db.commit()

    return WarmUpRespondResponse(message=greeting, is_complete=False)


@router.post("/sessions/{session_id}/warmup-respond", response_model=WarmUpRespondResponse)
async def warmup_respond(
    session_id: str,
    body: WarmUpRespondRequest,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
) -> WarmUpRespondResponse:
    detail = _get_session_detail(db, session_id)
    sm = SessionStateMachine(session_id=session_id, state=detail.state)
    persona = get_persona(detail.persona_id)

    conductor_warmup = WarmUpConductor(provider)
    stage = detail.warm_up_stage or "greeting"
    result = await conductor_warmup.respond_to_small_talk(body.text, stage, persona)
    detail.warm_up_stage = result.next_stage

    if not result.is_complete:
        db.commit()
        return WarmUpRespondResponse(message=result.text, is_complete=False)

    try:
        sm.fire("warm_up_complete")
    except InvalidTransitionError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    planned = _current_planned_question(detail)
    if planned is None:
        detail.state = sm.state
        db.commit()
        return WarmUpRespondResponse(message=result.text, is_complete=True)

    question, _section = planned
    conductor = InterviewConductor(provider)
    delivery = conductor.deliver_question(question, persona)
    sm.fire("question_delivered")

    turn = QuestionTurn(
        session_id=session_id, question_id=delivery.question_id, question_text=delivery.text
    )
    db.add(turn)
    detail.state = sm.state
    db.commit()

    return WarmUpRespondResponse(
        message=result.text,
        is_complete=True,
        first_question=delivery.text,
        question_id=delivery.question_id,
    )


@router.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    body: AnswerRequest,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_router),
) -> AnswerResponse:
    detail = _get_session_detail(db, session_id)
    sm = SessionStateMachine(session_id=session_id, state=detail.state)

    try:
        sm.fire("answer_received")
    except InvalidTransitionError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    open_turn = (
        db.query(QuestionTurn)
        .filter(QuestionTurn.session_id == session_id, QuestionTurn.answer_text.is_(None))
        .order_by(QuestionTurn.asked_at.desc())
        .first()
    )
    if open_turn is None:
        raise HTTPException(status_code=400, detail="No open question awaiting an answer")

    planned = _current_planned_question(detail)
    if planned is None:
        raise HTTPException(status_code=400, detail="No active plan question for this session")
    question, _section = planned

    persona = get_persona(detail.persona_id)
    conductor = InterviewConductor(provider)
    evaluation = await conductor.process_answer(body.text, question)

    open_turn.answer_text = body.text
    open_turn.evaluation_json = json.dumps(
        {
            "score": evaluation.score,
            "feedback": evaluation.feedback,
            "next_action": evaluation.next_action,
        }
    )
    open_turn.answered_at = datetime.now(timezone.utc)

    framework_missing = (
        evaluation.framework_analysis.missing if evaluation.framework_analysis else []
    )

    if evaluation.next_action == "follow_up":
        sm.fire("evaluation_needs_follow_up")
        follow_up_question = question.model_copy(
            update={"id": f"{question.id}-followup", "text": evaluation.follow_up_question or ""}
        )
        delivery = conductor.deliver_question(follow_up_question, persona, is_follow_up=True)
        sm.fire("follow_up_delivered")

        turn = QuestionTurn(
            session_id=session_id,
            question_id=delivery.question_id,
            question_text=delivery.text,
            is_follow_up=True,
        )
        db.add(turn)
        detail.state = sm.state
        db.commit()

        return AnswerResponse(
            score=evaluation.score,
            feedback=evaluation.feedback,
            reaction=evaluation.reaction,
            next_action="follow_up",
            next_message=delivery.text,
            next_question_id=delivery.question_id,
            framework_missing=framework_missing,
        )

    sm.fire("evaluation_next_question")
    has_more = _advance_question_index(detail)

    if not has_more:
        sm.fire("end_interview")
        sm.fire("wrap_up_questions")
        sm.fire("session_finalized")
        detail.state = sm.state
        detail.ended_at = datetime.now(timezone.utc)
        db.commit()
        return AnswerResponse(
            score=evaluation.score,
            feedback=evaluation.feedback,
            reaction=evaluation.reaction,
            next_action="session_complete",
            framework_missing=framework_missing,
        )

    next_planned = _current_planned_question(detail)
    assert next_planned is not None
    next_question, _next_section = next_planned
    delivery = conductor.deliver_question(next_question, persona)
    sm.fire("question_delivered")

    turn = QuestionTurn(
        session_id=session_id, question_id=delivery.question_id, question_text=delivery.text
    )
    db.add(turn)
    detail.state = sm.state
    db.commit()

    return AnswerResponse(
        score=evaluation.score,
        feedback=evaluation.feedback,
        reaction=evaluation.reaction,
        next_action="next_question",
        next_message=delivery.text,
        next_question_id=delivery.question_id,
        framework_missing=framework_missing,
    )


@router.post("/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: str, db: DBSession = Depends(get_db)) -> SessionResponse:
    detail = _get_session_detail(db, session_id)
    sm = SessionStateMachine(session_id=session_id, state=detail.state)

    try:
        if sm.is_in_progress or sm.state == "warm_up":
            sm.fire("end_interview")
        if sm.state == "wrapping_up":
            sm.fire("wrap_up_questions")
        if sm.state == "closing_chat":
            sm.fire("session_finalized")
    except InvalidTransitionError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    detail.state = sm.state
    detail.ended_at = datetime.now(timezone.utc)
    db.commit()

    # Auto-generate + cache the fused report so the session appears in History
    # immediately after completion (non-blocking: catches any errors gracefully).
    try:
        import asyncio
        asyncio.create_task(ReportService(db).get_report(session_id))
    except Exception:
        try:
            import asyncio as _aio
            import logging
            logger = logging.getLogger("poise.interview")
            logger.warning("Background report generation unavailable; caching inline")
            await ReportService(db).get_report(session_id)
        except Exception as exc:
            import logging
            logging.getLogger("poise.interview").warning(
                "Could not pre-cache report for %s: %s", session_id, exc
            )

    return SessionResponse(
        session_id=session_id,
        state=detail.state,
        persona_id=detail.persona_id,
        session_mode=detail.session_mode,
        plan=_load_plan(detail),
    )


@router.get("/sessions/{session_id}/evaluations", response_model=list[EvaluationRecordResponse])
def get_evaluations(
    session_id: str, db: DBSession = Depends(get_db)
) -> list[EvaluationRecordResponse]:
    _get_session_detail(db, session_id)  # 404s if the session doesn't exist
    turns = (
        db.query(QuestionTurn)
        .filter(QuestionTurn.session_id == session_id)
        .order_by(QuestionTurn.asked_at)
        .all()
    )

    results = []
    for turn in turns:
        evaluation = json.loads(turn.evaluation_json) if turn.evaluation_json else {}
        results.append(
            EvaluationRecordResponse(
                question_id=turn.question_id,
                question_text=turn.question_text,
                is_follow_up=turn.is_follow_up,
                answer_text=turn.answer_text,
                score=evaluation.get("score"),
                feedback=evaluation.get("feedback"),
            )
        )
    return results
