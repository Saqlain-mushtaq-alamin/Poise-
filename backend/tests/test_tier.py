"""Tier assignment rules against 10+ mocked hardware profiles, per the
Phase 2 spec's testing requirements table."""

from __future__ import annotations

import pytest

from app.services.hardware import GPUInfo, HardwareProfile
from app.services.tier import HardwareTier, recommend_tier


def _profile(**overrides) -> HardwareProfile:
    defaults = dict(
        os="windows",
        cpu_cores=8,
        cpu_name="Generic CPU",
        ram_total_gb=16.0,
        ram_available_gb=10.0,
        gpus=[],
        docker_available=True,
        ollama_available=True,
        ollama_models=[],
    )
    defaults.update(overrides)
    return HardwareProfile(**defaults)


def _gpu(vram_free_mb: int, vram_total_mb: int | None = None) -> GPUInfo:
    return GPUInfo(
        name="Test GPU",
        vram_total_mb=vram_total_mb or vram_free_mb,
        vram_available_mb=vram_free_mb,
        driver="nvidia",
    )


CASES = [
    # (description, profile, expected_tier)
    ("RTX 4060 8GB free", _profile(gpus=[_gpu(8192)]), HardwareTier.LOCAL_FULL),
    ("RTX 4090 24GB free", _profile(gpus=[_gpu(24000)]), HardwareTier.LOCAL_FULL),
    ("Exactly at 8GB boundary", _profile(gpus=[_gpu(8 * 1024)]), HardwareTier.LOCAL_FULL),
    ("Just under 8GB (7.9GB)", _profile(gpus=[_gpu(7000)]), HardwareTier.LOCAL_LITE),
    ("6GB GPU", _profile(gpus=[_gpu(6144)]), HardwareTier.LOCAL_LITE),
    ("Exactly at 4GB boundary", _profile(gpus=[_gpu(4096)]), HardwareTier.LOCAL_LITE),
    (
        "Just under 4GB (3.9GB), high RAM",
        _profile(gpus=[_gpu(3990)], ram_total_gb=32),
        HardwareTier.LOCAL_LITE,
    ),
    ("No GPU, 16GB RAM", _profile(gpus=[], ram_total_gb=16), HardwareTier.LOCAL_LITE),
    ("No GPU, 32GB RAM", _profile(gpus=[], ram_total_gb=32), HardwareTier.LOCAL_LITE),
    ("No GPU, 8GB RAM", _profile(gpus=[], ram_total_gb=8), HardwareTier.CLOUD_ASSIST),
    (
        "No GPU, 15.9GB RAM (just under)",
        _profile(gpus=[], ram_total_gb=15.9),
        HardwareTier.CLOUD_ASSIST,
    ),
    (
        "Weak GPU (2GB) + low RAM",
        _profile(gpus=[_gpu(2048)], ram_total_gb=8),
        HardwareTier.CLOUD_ASSIST,
    ),
    (
        "Multiple GPUs, best one qualifies for Local Full",
        _profile(gpus=[_gpu(2048), _gpu(12000)]),
        HardwareTier.LOCAL_FULL,
    ),
]


@pytest.mark.parametrize("description,profile,expected_tier", CASES, ids=[c[0] for c in CASES])
def test_tier_recommendation_matches_expected(description, profile, expected_tier):
    recommendation = recommend_tier(profile)
    assert recommendation.recommended_tier == expected_tier, description


def test_cloud_assist_is_always_in_available_tiers():
    for _, profile, _ in CASES:
        recommendation = recommend_tier(profile)
        assert HardwareTier.CLOUD_ASSIST in recommendation.available_tiers


def test_local_full_hardware_can_still_downgrade_to_every_tier():
    profile = _profile(gpus=[_gpu(16000)])
    recommendation = recommend_tier(profile)
    assert set(recommendation.available_tiers) == {
        HardwareTier.LOCAL_FULL,
        HardwareTier.LOCAL_LITE,
        HardwareTier.CLOUD_ASSIST,
    }


def test_cloud_assist_hardware_cannot_select_local_tiers():
    profile = _profile(gpus=[], ram_total_gb=8, ollama_available=False)
    recommendation = recommend_tier(profile)
    assert recommendation.available_tiers == [HardwareTier.CLOUD_ASSIST]


def test_low_ram_local_lite_gets_a_warning():
    profile = _profile(gpus=[_gpu(6144)], ram_total_gb=16)
    recommendation = recommend_tier(profile)
    assert any("slowdowns" in w.lower() for w in recommendation.warnings)


def test_no_docker_gets_a_warning_on_local_tiers():
    profile = _profile(gpus=[_gpu(8192)], docker_available=False)
    recommendation = recommend_tier(profile)
    assert any("docker" in w.lower() for w in recommendation.warnings)


def test_model_plan_matches_tier():
    profile = _profile(gpus=[_gpu(8192)])
    recommendation = recommend_tier(profile)
    assert recommendation.model_plan.vlm is not None  # Local Full has a VLM

    lite_profile = _profile(gpus=[_gpu(6144)])
    lite_recommendation = recommend_tier(lite_profile)
    assert lite_recommendation.model_plan.vlm is None  # Local Lite has no VLM
