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

from app.routers.hardware import ModelPlanResponse
from app.services.hardware import detect_hardware
from app.services.provider import ModelProviderRouter, ProviderError, get_router
from app.services.tier import HardwareTier

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
