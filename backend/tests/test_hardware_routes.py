"""HTTP-level tests for /hardware/* — hardware always mocked so results are
deterministic regardless of the machine running CI."""

from __future__ import annotations

from unittest.mock import patch

from app.services.hardware import GPUInfo, HardwareProfile


def _fake_profile(**overrides):
    defaults = dict(
        os="windows",
        cpu_cores=8,
        cpu_name="Test CPU",
        ram_total_gb=32.0,
        ram_available_gb=20.0,
        gpus=[
            GPUInfo(name="RTX 4060", vram_total_mb=8188, vram_available_mb=7200, driver="nvidia")
        ],
        docker_available=True,
        ollama_available=True,
        ollama_models=["qwen2.5:7b"],
    )
    defaults.update(overrides)
    return HardwareProfile(**defaults)


def _fake_full_tier_profile(**overrides):
    profile = _fake_profile(**overrides)
    profile.gpus = [
        GPUInfo(name="RTX 4090", vram_total_mb=24576, vram_available_mb=22000, driver="nvidia")
    ]
    return profile


def test_get_profile_returns_detected_hardware(client):
    with patch("app.routers.hardware.detect_hardware", return_value=_fake_profile()):
        resp = client.get("/hardware/profile")

    assert resp.status_code == 200
    body = resp.json()
    assert body["gpus"][0]["name"] == "RTX 4060"
    assert body["ollama_models"] == ["qwen2.5:7b"]


def test_get_tier_recommends_local_full_for_strong_gpu(client):
    with patch("app.routers.hardware.detect_hardware", return_value=_fake_full_tier_profile()):
        resp = client.get("/hardware/tier")

    assert resp.status_code == 200
    assert resp.json()["recommended_tier"] == "local_full"


def test_override_tier_rejects_unavailable_tier(client):
    weak_profile = _fake_profile(gpus=[], ram_total_gb=8.0)
    with patch("app.routers.hardware.detect_hardware", return_value=weak_profile):
        resp = client.put("/hardware/tier", json={"tier": "local_full"})

    assert resp.status_code == 400


def test_override_tier_persists_across_requests(client):
    with patch("app.routers.hardware.detect_hardware", return_value=_fake_profile()):
        put_resp = client.put("/hardware/tier", json={"tier": "local_lite"})
        assert put_resp.status_code == 200
        assert put_resp.json()["recommended_tier"] == "local_lite"

        get_resp = client.get("/hardware/tier")
        assert get_resp.json()["recommended_tier"] == "local_lite"
