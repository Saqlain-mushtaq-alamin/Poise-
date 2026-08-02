"""HTTP-level tests for the /setup/* first-run wizard, covering the full
detect -> recommend -> configure -> store-key -> test-connection ->
smoke-test flow with hardware/network calls mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.hardware import GPUInfo, HardwareProfile


def _fake_profile(**overrides):
    defaults = dict(
        os="linux",
        cpu_cores=16,
        cpu_name="Test CPU",
        ram_total_gb=32.0,
        ram_available_gb=24.0,
        gpus=[
            GPUInfo(name="RTX 4090", vram_total_mb=24576, vram_available_mb=22000, driver="nvidia")
        ],
        docker_available=True,
        ollama_available=False,
        ollama_models=[],
    )
    defaults.update(overrides)
    return HardwareProfile(**defaults)


def test_detect_hardware_step(client):
    with patch("app.routers.setup.detect_hardware", return_value=_fake_profile()):
        resp = client.post("/setup/detect-hardware")
    assert resp.status_code == 200
    assert resp.json()["cpu_cores"] == 16


def test_recommend_tier_step(client):
    with patch("app.routers.setup.detect_hardware", return_value=_fake_profile()):
        resp = client.post("/setup/recommend-tier")
    assert resp.status_code == 200
    assert resp.json()["recommended_tier"] == "local_full"


def test_configure_tier_step_persists_choice(client):
    with patch("app.routers.setup.detect_hardware", return_value=_fake_profile()):
        resp = client.post("/setup/configure-tier", json={"tier": {"tier": "local_lite"}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "local_lite"
    assert body["model_plan"]["vlm"] is None  # Local Lite has no VLM


def test_configure_tier_step_rejects_unavailable_tier(client):
    weak = _fake_profile(gpus=[], ram_total_gb=8.0)
    with patch("app.routers.setup.detect_hardware", return_value=weak):
        resp = client.post("/setup/configure-tier", json={"tier": {"tier": "local_full"}})
    assert resp.status_code == 400


def test_download_models_step_skips_when_ollama_not_running(client):
    with patch(
        "app.routers.setup.detect_hardware", return_value=_fake_profile(ollama_available=False)
    ):
        resp = client.post("/setup/download-models", json={"models": ["qwen2.5:7b"]})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "skipped" in body


def test_store_api_key_step(client):
    resp = client.post("/setup/store-api-key", json={"provider": "openai", "key": "sk-test"})
    assert resp.status_code == 200
    assert resp.json() == {"provider": "openai", "status": "stored"}


def test_store_api_key_step_rejects_unknown_provider(client):
    resp = client.post("/setup/store-api-key", json={"provider": "bogus", "key": "x"})
    assert resp.status_code == 400


def test_test_connection_step_fails_without_a_key(client):
    resp = client.post("/setup/test-connection", json={"provider": "openai"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "key" in body["error"].lower()


def test_test_connection_step_succeeds_with_mocked_http(client):
    fake_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]},
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/setup/test-connection", json={"provider": "openai", "key": "sk-test"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["models_available"] == 2
    assert body["latency_ms"] is not None


def test_test_connection_step_reports_http_error(client):
    fake_response = SimpleNamespace(status_code=401, json=lambda: {})

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/setup/test-connection", json={"provider": "openai", "key": "sk-bad"})

    body = resp.json()
    assert body["success"] is False
    assert "401" in body["error"]


def test_test_connection_step_requires_base_url_for_custom_provider(client):
    resp = client.post("/setup/test-connection", json={"provider": "custom", "key": "x"})
    body = resp.json()
    assert body["success"] is False
    assert "base_url" in body["error"]


def test_run_smoke_test_fails_gracefully_without_configuration(client):
    with patch("app.routers.setup.detect_hardware", return_value=_fake_profile(gpus=[], ram_total_gb=8.0)):
        client.post("/setup/configure-tier", json={"tier": {"tier": "cloud_assist"}})
    resp = client.post("/setup/run-smoke-test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"] is not None


def test_run_smoke_test_succeeds_with_mocked_provider(client):
    # Configure a cloud key first so the router has something to call.
    client.post("/setup/store-api-key", json={"provider": "openai", "key": "sk-test"})

    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ready"))],
        usage={"prompt_tokens": 5, "completion_tokens": 1},
    )

    with patch("litellm.acompletion", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/setup/run-smoke-test")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["sample_output"] == "ready"
    assert body["latency_ms"] is not None
