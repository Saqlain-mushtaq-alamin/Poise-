"""Tests for GET /health — the sidecar readiness contract Tauri relies on."""

from __future__ import annotations


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert isinstance(body["version"], str)
    assert body["uptime_seconds"] >= 0


def test_health_matches_contract_shape(client):
    body = client.get("/health").json()
    assert set(body.keys()) == {"status", "version", "database", "uptime_seconds"}
