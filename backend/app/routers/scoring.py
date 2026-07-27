"""
FastAPI router for Phase 8 (scoring & progress).

Registered in `app/main.py` alongside the other routers:

    from app.routers import scoring
    app.include_router(scoring.router)
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas.scoring import (
    CoverageMatrixOut,
    CoverageRequest,
    DebriefMessageOut,
    DebriefRequest,
    FusedReportOut,
    ModelAnswerRequest,
    ModelAnswerResponse,
    ReadinessVerdictOut,
    ReplayDataOut,
    SessionSummaryOut,
    TrendDataOut,
)
from app.services.scoring.debrief import DebriefService
from app.services.scoring.playbooks import IMPROVEMENT_PLAYBOOKS, match_playbooks
from app.services.scoring.report_service import ReportService

router = APIRouter(prefix="/scoring", tags=["scoring"])


def get_report_service(db: DBSession = Depends(get_db)) -> ReportService:
    return ReportService(db=db)


@router.get("/sessions/{session_id}/report", response_model=FusedReportOut)
async def get_report(
    session_id: str,
    refresh: bool = Query(False, description="Force recomputation instead of using the cache"),
    service: ReportService = Depends(get_report_service),
):
    report = await service.get_report(session_id, force_refresh=refresh)
    return asdict(report)


@router.get("/sessions/{session_id}/report/pdf")
async def get_report_pdf(
    session_id: str,
    service: ReportService = Depends(get_report_service),
):
    from app.services.scoring.pdf_export import render_report_pdf

    report = await service.get_report(session_id)
    pdf_bytes = render_report_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{session_id[:8]}.pdf"'},
    )


@router.get("/history", response_model=list[SessionSummaryOut])
async def get_history(
    mode: str | None = Query(None, description="Filter by 'interview' or 'ielts'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: ReportService = Depends(get_report_service),
):
    rows = service.list_history(mode=mode, limit=limit, offset=offset)
    return [
        SessionSummaryOut(
            session_id=r.session_id, mode=r.mode, overall_score=r.overall_score,
            duration_minutes=r.duration_minutes, persona_label=r.persona_label,
            jd_title=r.jd_title, generated_at=r.generated_at,
        )
        for r in rows
    ]


@router.get("/trends", response_model=TrendDataOut)
async def get_trends(
    mode: str | None = Query(None),
    last_n: int = Query(20, ge=2, le=100),
    service: ReportService = Depends(get_report_service),
):
    return service.get_trends(mode=mode, last_n=last_n)


@router.get("/readiness", response_model=ReadinessVerdictOut)
async def get_readiness(
    mode: str | None = Query(None),
    target_score: float = Query(75.0, ge=0, le=100),
    service: ReportService = Depends(get_report_service),
):
    verdict = await service.get_readiness(mode=mode, target_score=target_score)
    return verdict


@router.get("/sessions/{session_id}/replay", response_model=ReplayDataOut)
async def get_replay(
    session_id: str,
    service: ReportService = Depends(get_report_service),
):
    return await service.get_replay(session_id)


@router.post("/sessions/{session_id}/coverage", response_model=CoverageMatrixOut)
async def get_coverage(
    session_id: str,
    body: CoverageRequest,
    service: ReportService = Depends(get_report_service),
):
    matrix = await service.get_coverage(session_id, body.jd_text)
    return matrix


@router.post("/sessions/{session_id}/debrief", response_model=DebriefMessageOut)
async def post_debrief(
    session_id: str,
    body: DebriefRequest,
    db: DBSession = Depends(get_db),
    service: ReportService = Depends(get_report_service),
):
    report = await service.get_report(session_id)
    debrief = DebriefService(db=db)
    await debrief.start_or_continue(session_id, report)  # ensures an opening message exists
    reply = await debrief.reply(session_id, report, body.message)
    return reply


@router.get("/sessions/{session_id}/debrief", response_model=list[DebriefMessageOut])
async def get_debrief_history(
    session_id: str,
    db: DBSession = Depends(get_db),
    service: ReportService = Depends(get_report_service),
):
    report = await service.get_report(session_id)
    debrief = DebriefService(db=db)
    opening = await debrief.start_or_continue(session_id, report)
    history = debrief.get_history(session_id)
    return history or [opening]


@router.get("/playbooks")
async def get_all_playbooks():
    return IMPROVEMENT_PLAYBOOKS


@router.get("/sessions/{session_id}/playbooks")
async def get_session_playbooks(
    session_id: str,
    service: ReportService = Depends(get_report_service),
):
    report = await service.get_report(session_id)
    return match_playbooks(report)


@router.post("/sessions/{session_id}/questions/{question_index}/model-answer", response_model=ModelAnswerResponse)
async def post_model_answer(
    session_id: str,
    question_index: int,
    body: ModelAnswerRequest,
    service: ReportService = Depends(get_report_service),
):
    try:
        model_answer, diff = await service.get_model_answer(
            session_id, question_index, body.jd_summary, body.resume_summary
        )
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ModelAnswerResponse(model_answer=model_answer, diff=diff)
