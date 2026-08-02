"""Poise FastAPI sidecar entrypoint.

Run directly (``python -m app.main``) for local development, or invoke via
the compiled PyInstaller binary that Tauri spawns as a sidecar process in
production builds (see src-tauri/src/sidecar.rs).

On startup this binds to an OS-assigned free port (unless POISE_PORT is set)
and prints ``POISE_SIDECAR_PORT=<port>`` as the first line of stdout. The
Rust sidecar manager reads that line to learn which port to talk to.
"""

from __future__ import annotations

import os
import socket
import sys

os.environ["LITELLM_LOCAL_RESOURCES"] = "True"
os.environ["DISABLE_LITELLM_TELEMETRY"] = "True"

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure tables exist even before the first Alembic migration is run
    # (fresh installs). Alembic remains the source of truth for upgrades.
    # NOTE: `from app import models` (not `import app.models`) — the latter
    # would rebind the local `app` name and shadow the FastAPI instance above.
    from app import models  # noqa: F401  (registers ORM classes on Base.metadata)

    Base.metadata.create_all(bind=engine)

    from app.routers import (
        coding,
        hardware,
        health,
        ielts,
        interview,
        motivation,
        provider,
        scoring,
        setup,
        voice,
        webcam,
    )
    from app.routers import settings as settings_router

    app.include_router(health.router)
    app.include_router(settings_router.router)
    app.include_router(hardware.router)
    app.include_router(provider.router)
    app.include_router(setup.router)
    app.include_router(interview.router)
    app.include_router(ielts.router)
    app.include_router(coding.router)
    app.include_router(motivation.router)
    app.include_router(scoring.router)
    app.include_router(voice.router)
    app.include_router(webcam.router)

    return app


app = create_app()


def _is_port_available(port: int) -> bool:
    if port <= 0:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run() -> None:
    settings = get_settings()
    target_port = settings.port if _is_port_available(settings.port) else _find_free_port()

    # First stdout line: contract with src-tauri/src/sidecar.rs
    print(f"POISE_SIDECAR_PORT={target_port}", flush=True)

    uvicorn.run(
        app,
        host=settings.host,
        port=target_port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    sys.exit(run() or 0)
