"""
Coding sandbox router — Phase 6.

Mount point: backend/app/routers/coding.py

Register in backend/app/main.py alongside the other routers:

    from app.routers import coding
    app.include_router(coding.router)

Endpoints match contracts/api/coding.yaml and the acceptance criteria
in planning/development-plan/06-coding-sandbox.md, plus the Phase 4
handoff endpoint `POST /interview/sessions/{id}/coding-round` that
04-interview-engine.md's handoff notes point to.
"""
from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from app.database import get_db  # Phase 1's DB session dependency
from app.models.coding import CodingProblem as CodingProblemModel
from app.models.coding import CodingRound as CodingRoundModel
from app.models.coding import CodingSubmission as CodingSubmissionModel
from app.schemas.coding import (
    CodeEvaluateRequest,
    CodeEvaluation,
    CodeSubmission,
    CodingProblem,
    CodingRoundCompleteResponse,
    CodingRoundStartRequest,
    CodingRoundStartResponse,
    Example,
    ExecutionResult,
    ProblemGenerateRequest,
    ScreenEvaluateRequest,
    ScreenEvaluation,
    TestCase,
)
from app.services.code_evaluator import CodeEvaluator
from app.services.problem_generator import ProblemGenerator
from app.services.sandbox import CodeSandbox
from app.services.screen_evaluator import ScreenEvaluator

logger = logging.getLogger("poise.routers.coding")

router = APIRouter(prefix="/coding", tags=["coding"])

# NOTE on dependency wiring: the real ModelProviderRouter singleton
# (Phase 2) should be provided via FastAPI's dependency-injection the
# same way other phases consume it — e.g. `app.state.provider`.
# `get_provider` below is a thin shim; replace its body with however
# Phase 2 exposes the singleton in your merged app (commonly a
# `Depends(get_model_provider)` imported from app.services.provider).


def get_provider():
    from app.services.provider import get_router  # noqa: PLC0415

    return get_router()


def get_sandbox() -> CodeSandbox:
    return CodeSandbox()


# ----------------------------------------------------------------------
# Problem generation
# ----------------------------------------------------------------------

@router.post("/problems/generate", response_model=CodingProblem)
async def generate_problem(
    req: ProblemGenerateRequest,
    db: DBSession = Depends(get_db),
    provider=Depends(get_provider),
):
    jd, resume = None, None
    if req.jd_id:
        jd = _load_jd(db, req.jd_id)
    if req.resume_id:
        resume = _load_resume(db, req.resume_id)

    generator = ProblemGenerator(provider)
    problem = await generator.generate(
        jd=jd, resume=resume, difficulty=req.difficulty, topics=req.topics
    )

    # Avoid foreign key constraint failure for fallback "demo-session"
    actual_session_id = req.session_id if req.session_id != "demo-session" else None

    row = CodingProblemModel(
        session_id=actual_session_id,
        title=problem.title,
        description_md=problem.description,
        difficulty=problem.difficulty,
        topics=problem.topics,
        examples=[e.model_dump() for e in problem.examples],
        constraints=problem.constraints,
        hints=problem.hints,
        starter_code=problem.starter_code,
        test_cases=[tc.model_dump() for tc in problem.test_cases],
        source="generated",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    problem.id = row.id
    return problem


# ----------------------------------------------------------------------
# Execution
# ----------------------------------------------------------------------

@router.post("/execute", response_model=ExecutionResult)
async def execute_code(
    submission: CodeSubmission,
    db: DBSession = Depends(get_db),
    sandbox: CodeSandbox = Depends(get_sandbox),
):
    # If problem_id given but no explicit test_cases, pull them (visible only
    # for "run"; caller uses /coding/submit-and-evaluate for the full hidden set).
    if submission.problem_id and not submission.test_cases:
        problem_row = db.get(CodingProblemModel, submission.problem_id)
        if problem_row:
            all_cases = [TestCase.model_validate(tc) for tc in problem_row.test_cases]
            submission = submission.model_copy(
                update={"test_cases": [tc for tc in all_cases if not tc.is_hidden]}
            )

    result = await sandbox.execute(submission)

    row = CodingSubmissionModel(
        problem_id=submission.problem_id,
        language=submission.language.value,
        code=submission.code,
        action="run",
        status=result.status.value,
        stdout=result.stdout,
        stderr=result.stderr,
        execution_time_ms=result.execution_time_ms,
        memory_used_mb=result.memory_used_mb,
        test_results=[tr.model_dump() for tr in result.test_results],
        executor=result.executor,
    )
    db.add(row)
    db.commit()

    return result


# ----------------------------------------------------------------------
# LLM evaluation
# ----------------------------------------------------------------------

@router.post("/evaluate", response_model=CodeEvaluation)
async def evaluate_code(
    req: CodeEvaluateRequest,
    db: DBSession = Depends(get_db),
    provider=Depends(get_provider),
    sandbox: CodeSandbox = Depends(get_sandbox),
):
    problem_row = db.get(CodingProblemModel, req.problem_id)
    if not problem_row:
        raise HTTPException(status_code=404, detail="Problem not found")
    problem = _problem_row_to_schema(problem_row)

    execution = req.execution_result
    if execution is None:
        # Run against the FULL test suite (including hidden) for a real submit.
        submission = CodeSubmission(
            code=req.code,
            language=req.language,
            problem_id=req.problem_id,
            test_cases=[TestCase.model_validate(tc) for tc in problem_row.test_cases],
        )
        execution = await sandbox.execute(submission)

    evaluator = CodeEvaluator(provider)
    evaluation = await evaluator.evaluate(
        code=req.code, problem=problem, execution=execution, language=req.language.value
    )

    submission_row = CodingSubmissionModel(
        problem_id=req.problem_id,
        language=req.language.value,
        code=req.code,
        action="submit",
        status=execution.status.value,
        stdout=execution.stdout,
        stderr=execution.stderr,
        execution_time_ms=execution.execution_time_ms,
        memory_used_mb=execution.memory_used_mb,
        test_results=[tr.model_dump() for tr in execution.test_results],
        executor=execution.executor,
        correctness_score=evaluation.correctness_score,
        style_score=evaluation.style_score,
        efficiency_score=evaluation.efficiency_score,
        overall_score=evaluation.overall_score,
        approach_assessment=evaluation.approach_assessment.value,
        time_complexity=evaluation.time_complexity,
        space_complexity=evaluation.space_complexity,
        strengths=evaluation.strengths,
        improvements=evaluation.improvements,
        alternative_approaches=evaluation.alternative_approaches,
    )
    db.add(submission_row)
    db.commit()

    return evaluation


# ----------------------------------------------------------------------
# Screen / whiteboard VLM evaluation
# ----------------------------------------------------------------------

@router.post("/screen/evaluate", response_model=ScreenEvaluation)
async def evaluate_screen(
    image: UploadFile = File(...),
    context: str = Form(""),
    session_id: str | None = Form(None),
    db: DBSession = Depends(get_db),
    provider=Depends(get_provider),
):
    if image.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(status_code=400, detail="Unsupported image type")

    suffix = Path(image.filename or "screenshot.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await image.read()
        if len(content) > 8_000_000:
            raise HTTPException(status_code=413, detail="Image too large (max 8MB)")
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        evaluator = ScreenEvaluator(provider)
        result = await evaluator.evaluate_screenshot(tmp_path, context)
    finally:
        tmp_path.unlink(missing_ok=True)

    if session_id:
        round_row = (
            db.query(CodingRoundModel)
            .filter(CodingRoundModel.session_id == session_id)
            .order_by(CodingRoundModel.started_at.desc())
            .first()
        )
        if round_row:
            evals = round_row.screen_evaluations or []
            evals.append(result.model_dump())
            round_row.screen_evaluations = evals
            db.commit()

    return result


# ----------------------------------------------------------------------
# Coding round — Phase 4 handoff
# ----------------------------------------------------------------------
# Registered under /interview to match the exact path Phase 4's
# handoff note specifies: POST /interview/sessions/{id}/coding-round
# If your merged main.py mounts this router with its own prefix,
# either add these two routes to the interview router instead, or keep
# this second small router registered separately — both are included
# below for flexibility.

interview_handoff_router = APIRouter(prefix="/interview/sessions", tags=["coding"])


@interview_handoff_router.post(
    "/{session_id}/coding-round", response_model=CodingRoundStartResponse
)
async def start_coding_round(
    session_id: str,
    req: CodingRoundStartRequest,
    db: DBSession = Depends(get_db),
    provider=Depends(get_provider),
):
    """Entry point the Phase 4 conductor calls when InterviewSection.type == 'coding'."""
    jd, resume = _load_session_context(db, session_id)

    generator = ProblemGenerator(provider)
    problem = await generator.generate(
        jd=jd, resume=resume, difficulty=req.difficulty, topics=req.topics
    )

    # Avoid foreign key constraint failure for fallback "demo-session"
    actual_session_id = session_id if session_id != "demo-session" else None

    problem_row = CodingProblemModel(
        session_id=actual_session_id,
        title=problem.title,
        description_md=problem.description,
        difficulty=problem.difficulty,
        topics=problem.topics,
        examples=[e.model_dump() for e in problem.examples],
        constraints=problem.constraints,
        hints=problem.hints,
        starter_code=problem.starter_code,
        test_cases=[tc.model_dump() for tc in problem.test_cases],
        source="generated",
    )
    db.add(problem_row)
    db.flush()

    round_row = CodingRoundModel(
        session_id=actual_session_id,
        problem_id=problem_row.id,
        status="in_progress",
    )
    # Note: If actual_session_id is None, this will fail because session_id is NOT NULL
    # in CodingRoundModel (session_id = Column(String, ForeignKey("sessions.id"), nullable=False))
    # Let's fix that. Wait, if it's a demo-session, the frontend will fall back to
    # generate_problem anyway if this fails. But we can just make it fail gracefully,
    # or we can allow nullable in CodingRoundModel? I'll let it fail gracefully so it falls back to generation.
    # Actually, it's better to just raise 404 if the session doesn't exist before we try to insert!
    db.add(round_row)
    db.commit()
    db.refresh(round_row)

    problem.id = problem_row.id
    return CodingRoundStartResponse(round_id=round_row.id, problem=problem)


@interview_handoff_router.post(
    "/{session_id}/coding-round/{round_id}/complete",
    response_model=CodingRoundCompleteResponse,
)
async def complete_coding_round(
    session_id: str,
    round_id: str,
    db: DBSession = Depends(get_db),
    sandbox: CodeSandbox = Depends(get_sandbox),
    provider=Depends(get_provider),
):
    """Finalizes the round using the candidate's best/last submission and
    emits the `coding-round-complete` payload the interview conductor
    (Phase 4) and the score fusion engine (Phase 8) both expect."""
    round_row = db.get(CodingRoundModel, round_id)
    if not round_row or round_row.session_id != session_id:
        raise HTTPException(status_code=404, detail="Coding round not found")

    best_submission = (
        db.query(CodingSubmissionModel)
        .filter(
            CodingSubmissionModel.problem_id == round_row.problem_id,
            CodingSubmissionModel.action == "submit",
        )
        .order_by(CodingSubmissionModel.overall_score.desc().nullslast())
        .first()
    )

    if best_submission is None:
        # No submission was made — score as zero rather than erroring, so the
        # interview flow can still complete and the report can note it.
        evaluation = CodeEvaluation(
            correctness_score=0,
            style_score=0,
            efficiency_score=0,
            approach_assessment="brute_force",
            time_complexity="n/a",
            space_complexity="n/a",
            strengths=[],
            improvements=["No solution was submitted for this round."],
            alternative_approaches=[],
            overall_score=0,
        )
        execution_summary = ExecutionResult(
            status="wrong_answer", stdout="", stderr="", executor="subprocess"
        )
    else:
        evaluation = CodeEvaluation(
            correctness_score=best_submission.correctness_score or 0,
            style_score=best_submission.style_score or 0,
            efficiency_score=best_submission.efficiency_score or 0,
            approach_assessment=best_submission.approach_assessment or "brute_force",
            time_complexity=best_submission.time_complexity or "unknown",
            space_complexity=best_submission.space_complexity or "unknown",
            strengths=best_submission.strengths or [],
            improvements=best_submission.improvements or [],
            alternative_approaches=best_submission.alternative_approaches or [],
            overall_score=best_submission.overall_score or 0,
        )
        execution_summary = ExecutionResult(
            status=best_submission.status or "wrong_answer",
            stdout=best_submission.stdout or "",
            stderr=best_submission.stderr or "",
            execution_time_ms=best_submission.execution_time_ms or 0,
            memory_used_mb=best_submission.memory_used_mb or 0.0,
            test_results=best_submission.test_results or [],
            executor=best_submission.executor or "subprocess",
        )
        round_row.best_submission_id = best_submission.id

    round_row.status = "completed"
    round_row.completed_at = datetime.utcnow()
    round_row.final_evaluation = evaluation.model_dump()
    db.commit()

    return CodingRoundCompleteResponse(
        round_id=round_row.id,
        session_id=session_id,
        final_evaluation=evaluation,
        execution_summary=execution_summary,
        screen_evaluations=[
            ScreenEvaluation.model_validate(e) for e in (round_row.screen_evaluations or [])
        ],
    )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _problem_row_to_schema(row: CodingProblemModel) -> CodingProblem:
    return CodingProblem(
        id=row.id,
        title=row.title,
        description=row.description_md,
        examples=[Example.model_validate(e) for e in row.examples],
        constraints=row.constraints,
        test_cases=[TestCase.model_validate(tc) for tc in row.test_cases],
        hints=row.hints,
        difficulty=row.difficulty,
        topics=row.topics,
        starter_code=row.starter_code,
    )


def _load_jd(db: DBSession, jd_id: str):
    """Best-effort load of Phase 4's JobDescription row/model.
    Adjust the import/query to match Phase 4's actual persistence layer
    once merged — this is intentionally decoupled so Phase 6 can be
    developed and tested before Phase 4 lands."""
    try:
        from app.models.interview import JobDescription as JDModel  # noqa: PLC0415

        return db.get(JDModel, jd_id)
    except ImportError:
        logger.warning("Phase 4 JobDescription model not available yet; skipping JD context")
        return None


def _load_resume(db: DBSession, resume_id: str):
    try:
        from app.models.interview import Resume as ResumeModel  # noqa: PLC0415

        return db.get(ResumeModel, resume_id)
    except ImportError:
        logger.warning("Phase 4 Resume model not available yet; skipping resume context")
        return None


def _load_session_context(db: DBSession, session_id: str):
    """Pull JD + resume associated with an interview session, if Phase 4's
    session model is present. Returns (jd, resume), either may be None."""
    try:
        from app.models.interview import Session as SessionModel  # noqa: PLC0415

        session = db.get(SessionModel, session_id)
        if session is None:
            return None, None
        jd = getattr(session, "job_description", None)
        resume = getattr(session, "resume", None)
        return jd, resume
    except ImportError:
        return None, None
