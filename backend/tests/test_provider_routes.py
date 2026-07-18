"""HTTP-level tests for /provider/*."""

from __future__ import annotations


def test_status_reflects_default_tier(client):
    resp = client.get("/provider/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "tier" in body
    assert "model_plan" in body


def test_set_and_clear_api_key(client):
    put_resp = client.put("/provider/keys/openai", json={"key": "sk-test-abc"})
    assert put_resp.status_code == 200
    assert put_resp.json() == {"provider": "openai", "status": "stored"}

    status_resp = client.get("/provider/status")
    assert "openai" in status_resp.json()["configured_providers"]

    del_resp = client.delete("/provider/keys/openai")
    assert del_resp.json()["status"] == "cleared"

    status_resp_2 = client.get("/provider/status")
    assert "openai" not in status_resp_2.json()["configured_providers"]


def test_set_api_key_rejects_unknown_provider(client):
    resp = client.put("/provider/keys/not-a-provider", json={"key": "x"})
    assert resp.status_code == 400


def test_cost_estimate_starts_empty(client):
    resp = client.get("/provider/cost")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] >= 0
    assert body["cap_warning"] is False


def test_set_cost_cap_updates_estimate_response(client):
    resp = client.put("/provider/cost/cap", json={"soft_cap_tokens": 100, "soft_cap_usd": 0.01})
    assert resp.status_code == 200
    assert resp.json()["soft_cap_tokens"] == 100
    assert resp.json()["soft_cap_usd"] == 0.01
