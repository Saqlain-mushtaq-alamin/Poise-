"""Tests for database connectivity + Alembic-managed schema creation."""

from __future__ import annotations


def test_database_is_connected_after_app_creation(client):
    from app.database import database_is_connected

    assert database_is_connected() is True


def test_sessions_table_exists(client, isolated_data_dir):
    import sqlite3

    db_path = isolated_data_dir / "poise.db"
    con = sqlite3.connect(db_path)
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()

    assert "sessions" in tables
    assert "app_settings" in tables
