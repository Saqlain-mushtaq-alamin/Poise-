"""Poise FastAPI sidecar entrypoint.

Run directly (``python -m app.main``) for local development, or invoke via
the compiled PyInstaller binary that Tauri spawns as a sidecar process in
production builds (see src-tauri/src/sidecar.rs).

On startup this binds to an OS-assigned free port (unless POISE_PORT is set)
and prints ``POISE_SIDECAR_PORT=<port>`` as the first line of stdout. The
Rust sidecar manager reads that line to learn which port to talk to.
"""

from __future__ import annotations

import socket
import sys

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

    from app.routers import hardware, health, provider, setup
    from app.routers import settings as settings_router

    app.include_router(health.router)
    app.include_router(settings_router.router)
    app.include_router(hardware.router)
    app.include_router(provider.router)
    app.include_router(setup.router)

    return app


app = create_app()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run() -> None:
    settings = get_settings()
    port = settings.port or _find_free_port()

    # First stdout line: contract with src-tauri/src/sidecar.rs
    print(f"POISE_SIDECAR_PORT={port}", flush=True)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    sys.exit(run() or 0)
