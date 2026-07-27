"""Phase 9.6 — backend error categories, mirrored 1:1 with
frontend/src/lib/errors.ts so the sidecar can send a `category` field the
frontend already knows how to render without guessing from message text.

Merge notes:
- If backend/app/main.py already registers exception handlers, add
  `register_error_handlers(app)` to that factory rather than creating a
  second FastAPI instance.
- Raise `PoiseAPIError` anywhere in routers/services instead of a bare
  HTTPException when you want a specific user-facing category.
"""

from __future__ import annotations

from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErrorCategory(str, Enum):
    SIDECAR_CRASH = "SIDECAR_CRASH"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    GPU_OUT_OF_MEMORY = "GPU_OUT_OF_MEMORY"
    CLOUD_AUTH_FAILED = "CLOUD_AUTH_FAILED"
    CLOUD_RATE_LIMIT = "CLOUD_RATE_LIMIT"
    MIC_PERMISSION = "MIC_PERMISSION"
    CAMERA_PERMISSION = "CAMERA_PERMISSION"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


class PoiseAPIError(Exception):
    def __init__(self, category: ErrorCategory, detail: str | None = None, status_code: int = 500):
        self.category = category
        self.detail = detail or category.value
        self.status_code = status_code
        super().__init__(self.detail)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PoiseAPIError)
    async def _poise_error_handler(_: Request, exc: PoiseAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"category": exc.category.value, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def _fallback_handler(_: Request, exc: Exception) -> JSONResponse:
        # Anything unclassified still reaches the frontend with enough shape
        # for classifyError() to fall back to UNKNOWN gracefully.
        return JSONResponse(
            status_code=500,
            content={"category": ErrorCategory.UNKNOWN.value, "detail": str(exc)},
        )
