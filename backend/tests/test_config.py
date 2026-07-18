"""Tests for Settings loading and derived paths."""

from __future__ import annotations

from pathlib import Path


def test_settings_creates_data_dir(isolated_data_dir):
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert Path(settings.data_dir) == isolated_data_dir
    assert settings.data_dir.exists()


def test_database_url_points_inside_data_dir(isolated_data_dir):
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert str(settings.data_dir) in settings.database_url
    assert settings.database_url.startswith("sqlite:///")
