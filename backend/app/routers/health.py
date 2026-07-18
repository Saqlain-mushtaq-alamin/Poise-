"""Health check endpoint — used by Tauri sidecar manager to confirm the
FastAPI process is alive and the database is reachable."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.config import Settings, get_settings
from app.database import database_is_connected, get_db

router = APIRouter(tags=["health"])

_process_start = time.monotonic()


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    uptime_seconds: float


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    db: DBSession = Depends(get_db),
) -> HealthResponse:
    # `db` dependency ensures a connection round-trip is exercised too.
    connected = database_is_connected()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        database="connected" if connected else "disconnected",
        uptime_seconds=round(time.monotonic() - _process_start, 3),
    )
