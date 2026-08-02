"""GET /provider/status, GET /provider/cost, PUT /provider/keys/{provider}.

The keys endpoint is the receiving end of the BYOK flow: the Rust side
reads a key out of the OS keychain and PUTs it here so this in-memory
process can use it — see src-tauri/src/keychain.rs. It is intentionally not
exposed over anything but localhost (enforced by the sidecar binding to
127.0.0.1 — see app/config.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.models.settings import AppSettings
from app.routers.hardware import ModelPlanResponse
from app.services.hardware import detect_hardware
from app.services.provider import ModelProviderRouter, ProviderError, get_router
from app.services.tier import HardwareTier
from sqlalchemy.orm import Session as DBSession

router = APIRouter(prefix="/provider", tags=["provider"])


class ProviderStatusResponse(BaseModel):
    tier: HardwareTier
    model_plan: ModelPlanResponse
    configured_providers: list[str]
    ollama_reachable: bool


class CostEstimateResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    soft_cap_tokens: int
    soft_cap_usd: float
    cap_warning: bool


class SetApiKeyRequest(BaseModel):
    key: str
    base_url: str | None = None


class SetApiKeyResponse(BaseModel):
    provider: str
    status: str


class CostCapRequest(BaseModel):
    soft_cap_tokens: int
    soft_cap_usd: float


class SetModelRequest(BaseModel):
    model: str | None


class ModelConfigResponse(BaseModel):
    selected_model: str
    available_models: list[str]


@router.get("/status", response_model=ProviderStatusResponse)
def get_provider_status(
    provider_router: ModelProviderRouter = Depends(get_router),
) -> ProviderStatusResponse:
    profile = detect_hardware()
    status = provider_router.status(ollama_reachable=profile.ollama_available)
    return ProviderStatusResponse(
        tier=status.tier,
        model_plan=ModelPlanResponse.from_dataclass(status.model_plan),
        configured_providers=status.configured_providers,
        ollama_reachable=status.ollama_reachable,
    )


@router.get("/cost", response_model=CostEstimateResponse)
def get_cost_estimate(
    provider_router: ModelProviderRouter = Depends(get_router),
) -> CostEstimateResponse:
    estimate = provider_router.get_cost_estimate()
    return CostEstimateResponse(**estimate.__dict__)


@router.put("/cost/cap", response_model=CostEstimateResponse)
def set_cost_cap(
    body: CostCapRequest,
    provider_router: ModelProviderRouter = Depends(get_router),
) -> CostEstimateResponse:
    provider_router.token_tracker.soft_cap_tokens = body.soft_cap_tokens
    provider_router.token_tracker.soft_cap_usd = body.soft_cap_usd
    estimate = provider_router.get_cost_estimate()
    return CostEstimateResponse(**estimate.__dict__)


@router.put("/keys/{provider}", response_model=SetApiKeyResponse)
def set_api_key(
    provider: str,
    body: SetApiKeyRequest,
    provider_router: ModelProviderRouter = Depends(get_router),
) -> SetApiKeyResponse:
    try:
        provider_router.set_api_key(provider, body.key, base_url=body.base_url)
    except ProviderError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return SetApiKeyResponse(provider=provider, status="stored")


@router.delete("/keys/{provider}", response_model=SetApiKeyResponse)
def clear_api_key(
    provider: str,
    provider_router: ModelProviderRouter = Depends(get_router),
) -> SetApiKeyResponse:
    provider_router.clear_api_key(provider)
    return SetApiKeyResponse(provider=provider, status="cleared")


@router.get("/model", response_model=ModelConfigResponse)
def get_model_config(
    db: DBSession = Depends(get_db),
    provider_router: ModelProviderRouter = Depends(get_router),
) -> ModelConfigResponse:
    profile = detect_hardware()
    saved = db.get(AppSettings, "selected_llm_model")
    override = saved.value if saved else provider_router.get_model_override()
    if override:
        provider_router.set_model_override(override)

    selected = provider_router.model_plan.llm
    available = profile.ollama_models if profile.ollama_available else []
    return ModelConfigResponse(selected_model=selected, available_models=available)


@router.put("/model", response_model=ModelConfigResponse)
def set_model_config(
    body: SetModelRequest,
    db: DBSession = Depends(get_db),
    provider_router: ModelProviderRouter = Depends(get_router),
) -> ModelConfigResponse:
    profile = detect_hardware()
    row = db.get(AppSettings, "selected_llm_model")
    if body.model:
        if row is None:
            row = AppSettings(key="selected_llm_model", value=body.model)
            db.add(row)
        else:
            row.value = body.model
        provider_router.set_model_override(body.model)
    else:
        if row:
            db.delete(row)
        provider_router.set_model_override(None)
    db.commit()

    selected = provider_router.model_plan.llm
    available = profile.ollama_models if profile.ollama_available else []
    return ModelConfigResponse(selected_model=selected, available_models=available)
