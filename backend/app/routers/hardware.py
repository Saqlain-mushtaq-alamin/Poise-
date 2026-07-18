"""GET /hardware/profile, GET+PUT /hardware/tier.

Tier overrides persist through the existing generic settings table (key
`hardware_tier_override`) rather than a bespoke column — Phase 1's
AppSettings model already does exactly what this needs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.settings import AppSettings
from app.services.hardware import GPUInfo, HardwareProfile, detect_hardware
from app.services.provider import ModelProviderRouter, get_router
from app.services.tier import HardwareTier, ModelPlan, TierRecommendation, recommend_tier

router = APIRouter(prefix="/hardware", tags=["hardware"])

TIER_OVERRIDE_KEY = "hardware_tier_override"


class GPUInfoResponse(BaseModel):
    name: str
    vram_total_mb: int
    vram_available_mb: int
    driver: str
    compute_capability: str | None = None

    @classmethod
    def from_dataclass(cls, gpu: GPUInfo) -> GPUInfoResponse:
        return cls(**gpu.__dict__)


class HardwareProfileResponse(BaseModel):
    os: str
    cpu_cores: int
    cpu_name: str
    ram_total_gb: float
    ram_available_gb: float
    gpus: list[GPUInfoResponse]
    docker_available: bool
    ollama_available: bool
    ollama_models: list[str]

    @classmethod
    def from_dataclass(cls, profile: HardwareProfile) -> HardwareProfileResponse:
        return cls(
            os=profile.os,
            cpu_cores=profile.cpu_cores,
            cpu_name=profile.cpu_name,
            ram_total_gb=profile.ram_total_gb,
            ram_available_gb=profile.ram_available_gb,
            gpus=[GPUInfoResponse.from_dataclass(g) for g in profile.gpus],
            docker_available=profile.docker_available,
            ollama_available=profile.ollama_available,
            ollama_models=profile.ollama_models,
        )


class ModelPlanResponse(BaseModel):
    llm: str
    vlm: str | None
    stt: str
    tts: str
    embedding: str

    @classmethod
    def from_dataclass(cls, plan: ModelPlan) -> ModelPlanResponse:
        return cls(**plan.__dict__)


class TierRecommendationResponse(BaseModel):
    recommended_tier: HardwareTier
    reason: str
    available_tiers: list[HardwareTier]
    model_plan: ModelPlanResponse
    warnings: list[str]

    @classmethod
    def from_dataclass(cls, rec: TierRecommendation) -> TierRecommendationResponse:
        return cls(
            recommended_tier=rec.recommended_tier,
            reason=rec.reason,
            available_tiers=rec.available_tiers,
            model_plan=ModelPlanResponse.from_dataclass(rec.model_plan),
            warnings=rec.warnings,
        )


class TierOverrideRequest(BaseModel):
    tier: HardwareTier


@router.get("/profile", response_model=HardwareProfileResponse)
def get_hardware_profile() -> HardwareProfileResponse:
    return HardwareProfileResponse.from_dataclass(detect_hardware())


@router.get("/tier", response_model=TierRecommendationResponse)
def get_current_tier(
    db: DBSession = Depends(get_db),
    provider_router: ModelProviderRouter = Depends(get_router),
) -> TierRecommendationResponse:
    override = db.get(AppSettings, TIER_OVERRIDE_KEY)
    profile = detect_hardware()
    recommendation = recommend_tier(profile)

    if override and override.value in {t.value for t in HardwareTier}:
        chosen_tier = HardwareTier(override.value)
        provider_router.set_tier(chosen_tier)
        recommendation.recommended_tier = chosen_tier
        recommendation.model_plan = provider_router.model_plan

    return TierRecommendationResponse.from_dataclass(recommendation)


@router.put("/tier", response_model=TierRecommendationResponse)
def override_tier(
    body: TierOverrideRequest,
    db: DBSession = Depends(get_db),
    provider_router: ModelProviderRouter = Depends(get_router),
) -> TierRecommendationResponse:
    profile = detect_hardware()
    recommendation = recommend_tier(profile)

    if body.tier not in recommendation.available_tiers:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tier '{body.tier.value}' is not available on this hardware. "
                f"Available: {[t.value for t in recommendation.available_tiers]}"
            ),
        )

    row = db.get(AppSettings, TIER_OVERRIDE_KEY)
    if row is None:
        row = AppSettings(key=TIER_OVERRIDE_KEY, value=body.tier.value)
        db.add(row)
    else:
        row.value = body.tier.value
    db.commit()

    provider_router.set_tier(body.tier)
    recommendation.recommended_tier = body.tier
    recommendation.model_plan = provider_router.model_plan

    return TierRecommendationResponse.from_dataclass(recommendation)
