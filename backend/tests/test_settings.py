"""Tests for the generic key/value settings endpoints (theme persistence)."""

from __future__ import annotations


def test_get_missing_setting_returns_none(client):
    resp = client.get("/settings/theme")
    assert resp.status_code == 200
    assert resp.json() == {"value": None}


def test_put_then_get_roundtrips(client):
    put_resp = client.put("/settings/theme", json={"value": "dark"})
    assert put_resp.status_code == 200
    assert put_resp.json() == {"value": "dark"}

    get_resp = client.get("/settings/theme")
    assert get_resp.json() == {"value": "dark"}


def test_put_overwrites_existing_value(client):
    client.put("/settings/theme", json={"value": "dark"})
    resp = client.put("/settings/theme", json={"value": "light"})
    assert resp.json() == {"value": "light"}
    assert client.get("/settings/theme").json() == {"value": "light"}
