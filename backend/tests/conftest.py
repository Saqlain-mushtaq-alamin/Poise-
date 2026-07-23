"""Shared pytest fixtures. Each test run gets an isolated temp data dir so
tests never touch the real per-user Poise database."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("POISE_DATA_DIR", str(tmp_path))
    # Settings/engine are cached at import time in some modules under test,
    # so tests that need a fresh engine should re-import app.database.
    yield tmp_path


@pytest.fixture()
def client(isolated_data_dir):
    import sys

    from fastapi.testclient import TestClient

    # `app.database` binds a module-level `engine` at import time from
    # cached Settings. Drop every `app.*` module so each test gets a fresh
    # engine bound to its own isolated_data_dir instead of a stale one.
    #
    # PITFALL this creates: any `app.*` class imported *inside a test
    # function body* (rather than at module top level) after this fixture
    # has already run once in the same test session will be a *different*
    # class object than the one modules imported at collection time are
    # using — `isinstance`/`pytest.raises` checks against it will then
    # silently fail to match. Always import `app.*` names you'll use in
    # `pytest.raises(...)` or other identity/isinstance checks at the top
    # of the test file, never inside the test function.
    for mod in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[mod]

    from app.main import create_app

    fastapi_app = create_app()
    with TestClient(fastapi_app) as c:
        yield c
