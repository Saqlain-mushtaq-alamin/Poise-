"""Tier assignment.

Turns a `HardwareProfile` into a `TierRecommendation`: which tier we'd pick
by default, which tiers the user is *allowed* to pick instead, and which
models to run for each role at that tier.

Kept as pure functions (no I/O) so the 10+ profile-to-tier test matrix in
Phase 2's spec can run instantly and deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.hardware import HardwareProfile

# Tier thresholds, from the Phase 2 spec's "Tier rules" table.
# We use 7.5GB (not 8GB) as the Local Full threshold to account for GPU
# driver VRAM overhead — a nominal 8GB card (e.g. RTX 4060) reports ~7.9-8.0GB.
LOCAL_FULL_MIN_VRAM_MB = 7 * 1024 + 500   # 7.5 GB
LOCAL_LITE_MIN_VRAM_MB = 4 * 1024          # 4 GB
LOCAL_LITE_MIN_RAM_GB = 16.0


class HardwareTier(str, Enum):
    LOCAL_FULL = "local_full"
    LOCAL_LITE = "local_lite"
    CLOUD_ASSIST = "cloud_assist"


@dataclass
class ModelPlan:
    llm: str
    stt: str
    tts: str
    embedding: str
    vlm: str | None = None


# Model plans per tier. Local tiers assume Ollama is present; Phase 3/6/7
# developers should treat these strings as defaults, not guarantees — the
# actual model that ends up loaded also depends on what's already pulled
# (see HardwareProfile.ollama_models).
_MODEL_PLANS: dict[HardwareTier, ModelPlan] = {
    HardwareTier.LOCAL_FULL: ModelPlan(
        llm="qwen2.5:14b-instruct-q4_K_M",  # Best for 8GB+ VRAM; fallback to smaller if not pulled
        vlm="llava:7b",                      # Vision model (already available)
        stt="large-v3",
        tts="xtts-v2",
        embedding="nomic-embed-text",
    ),
    HardwareTier.LOCAL_LITE: ModelPlan(
        llm="qwen3:8b",                      # Fast, fits in 4-8GB VRAM
        vlm=None,
        stt="small",
        tts="piper",
        embedding="nomic-embed-text",
    ),
    HardwareTier.CLOUD_ASSIST: ModelPlan(
        llm="gpt-4o-mini",
        vlm="gpt-4o",
        stt="whisper-1",
        tts="tts-1",
        embedding="text-embedding-3-small",
    ),
}


@dataclass
class TierRecommendation:
    recommended_tier: HardwareTier
    reason: str
    available_tiers: list[HardwareTier]
    model_plan: ModelPlan
    warnings: list[str] = field(default_factory=list)


def _best_gpu_vram_mb(profile: HardwareProfile) -> tuple[int, int]:
    """Returns (total_mb, free_mb) for the best GPU."""
    if not profile.gpus:
        return 0, 0
    best = max(profile.gpus, key=lambda g: g.vram_total_mb)
    return best.vram_total_mb, best.vram_available_mb


def recommend_tier(profile: HardwareProfile) -> TierRecommendation:
    """Classify a hardware profile per the Phase 2 tier rules table.

    Uses TOTAL VRAM (not free) for tier thresholds: Ollama manages its own
    VRAM allocation, so the full card capacity is what matters, not whatever
    is currently free from other running processes.

    | Condition                                   | Tier          |
    |----------------------------------------------|---------------|
    | Any GPU with >=8GB total VRAM (or >=7GB free) | Local Full    |
    | GPU with 4-7GB or CPU with >=16GB RAM          | Local Lite    |
    | Everything else                                | Cloud Assist  |
    """
    total_vram_mb, free_vram_mb = _best_gpu_vram_mb(profile)
    warnings: list[str] = []

    # Use the larger of total/free so a card with most VRAM in use (e.g. by
    # a running game) doesn't incorrectly downgrade to local_lite at startup.
    effective_vram_mb = max(total_vram_mb, free_vram_mb)

    if effective_vram_mb >= LOCAL_FULL_MIN_VRAM_MB:
        tier = HardwareTier.LOCAL_FULL
        reason = (
            f"Detected {total_vram_mb / 1024:.1f}GB GPU ({free_vram_mb / 1024:.1f}GB free). "
            "Running full local models via Ollama."
        )
    elif effective_vram_mb >= LOCAL_LITE_MIN_VRAM_MB:
        tier = HardwareTier.LOCAL_LITE
        reason = f"Detected {total_vram_mb / 1024:.1f}GB GPU (4–7GB range)."
    elif profile.ram_total_gb >= LOCAL_LITE_MIN_RAM_GB:
        tier = HardwareTier.LOCAL_LITE
        reason = (
            f"No capable GPU detected, but {profile.ram_total_gb:.0f}GB system RAM "
            "supports CPU-offloaded local inference."
        )
        warnings.append("Running without a GPU will be noticeably slower than Local Full.")
    else:
        tier = HardwareTier.CLOUD_ASSIST
        reason = "Insufficient local compute (no capable GPU, <16GB RAM) — bring your own API key."

    if not profile.docker_available and tier != HardwareTier.CLOUD_ASSIST:
        warnings.append(
            "Docker not detected — local model serving will use the subprocess fallback."
        )

    if tier == HardwareTier.LOCAL_LITE and profile.ram_total_gb < 24:
        warnings.append("Low RAM may cause slowdowns when other apps are also running.")

    # Ollama bonus: if Ollama is reachable and has models, ensure local tiers
    # are in the available list even if GPU thresholds weren't met.
    if profile.ollama_available and profile.ollama_models:
        if tier == HardwareTier.CLOUD_ASSIST:
            # Surprise upgrade — user has Ollama running, give them local_lite
            tier = HardwareTier.LOCAL_LITE
            reason = (
                f"Ollama detected with {len(profile.ollama_models)} model(s). "
                "Using local inference (CPU offload mode)."
            )

    available = [HardwareTier.CLOUD_ASSIST]
    if effective_vram_mb >= LOCAL_LITE_MIN_VRAM_MB or profile.ram_total_gb >= LOCAL_LITE_MIN_RAM_GB or profile.ollama_available:
        available.append(HardwareTier.LOCAL_LITE)
    if effective_vram_mb >= LOCAL_FULL_MIN_VRAM_MB:
        available.append(HardwareTier.LOCAL_FULL)
    available.sort(key=lambda t: list(HardwareTier).index(t))

    return TierRecommendation(
        recommended_tier=tier,
        reason=reason,
        available_tiers=available,
        model_plan=_MODEL_PLANS[tier],
        warnings=warnings,
    )


import dataclasses


def model_plan_for(tier: HardwareTier) -> ModelPlan:
    return dataclasses.replace(_MODEL_PLANS[tier])
