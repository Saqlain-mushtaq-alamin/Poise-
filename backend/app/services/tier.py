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
LOCAL_FULL_MIN_VRAM_MB = 8 * 1024
LOCAL_LITE_MIN_VRAM_MB = 4 * 1024
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
        llm="qwen2.5:14b-instruct-q4_K_M",
        vlm="qwen2-vl:7b-q4",
        stt="large-v3",
        tts="xtts-v2",
        embedding="nomic-embed-text",
    ),
    HardwareTier.LOCAL_LITE: ModelPlan(
        llm="qwen2.5:7b-instruct-q4_K_M",
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


def _best_gpu_free_vram_mb(profile: HardwareProfile) -> int:
    if not profile.gpus:
        return 0
    return max(gpu.vram_available_mb for gpu in profile.gpus)


def recommend_tier(profile: HardwareProfile) -> TierRecommendation:
    """Classify a hardware profile per the Phase 2 tier rules table:

    | Condition                                   | Tier          |
    |----------------------------------------------|---------------|
    | Any GPU with >=8GB free VRAM                  | Local Full    |
    | GPU with 4-7GB or CPU with >=16GB RAM          | Local Lite    |
    | Everything else                                | Cloud Assist  |
    """
    free_vram_mb = _best_gpu_free_vram_mb(profile)
    warnings: list[str] = []

    if free_vram_mb >= LOCAL_FULL_MIN_VRAM_MB:
        tier = HardwareTier.LOCAL_FULL
        reason = f"Detected {free_vram_mb / 1024:.1f}GB free VRAM (>=8GB threshold)."
    elif free_vram_mb >= LOCAL_LITE_MIN_VRAM_MB:
        tier = HardwareTier.LOCAL_LITE
        reason = f"Detected {free_vram_mb / 1024:.1f}GB free VRAM (4-7GB range)."
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

    # Users can always downgrade to a cheaper/lighter tier, or upgrade if
    # their hardware supports it. Cloud Assist is always available as an
    # escape hatch (it needs a BYOK key, not local resources).
    available = [HardwareTier.CLOUD_ASSIST]
    if free_vram_mb >= LOCAL_LITE_MIN_VRAM_MB or profile.ram_total_gb >= LOCAL_LITE_MIN_RAM_GB:
        available.append(HardwareTier.LOCAL_LITE)
    if free_vram_mb >= LOCAL_FULL_MIN_VRAM_MB:
        available.append(HardwareTier.LOCAL_FULL)
    available.sort(key=lambda t: list(HardwareTier).index(t))

    return TierRecommendation(
        recommended_tier=tier,
        reason=reason,
        available_tiers=available,
        model_plan=_MODEL_PLANS[tier],
        warnings=warnings,
    )


def model_plan_for(tier: HardwareTier) -> ModelPlan:
    return _MODEL_PLANS[tier]
