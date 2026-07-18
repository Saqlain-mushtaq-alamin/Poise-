"""First-run wizard backend.

Endpoints exactly as listed in the Phase 2 spec's §2.5:

    POST /setup/detect-hardware
    POST /setup/recommend-tier
    POST /setup/configure-tier
    POST /setup/download-models     (SSE)
    POST /setup/store-api-key
    POST /setup/test-connection
    POST /setup/run-smoke-test

These are POST (not GET) because the wizard is a guided, stateful flow —
each step can have side effects (persisting the chosen tier, storing a key)
even where the underlying data could technically be read with a GET.
"""

from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.settings import AppSettings
from app.routers.hardware import (
    TIER_OVERRIDE_KEY,
    HardwareProfileResponse,
    ModelPlanResponse,
    TierOverrideRequest,
    TierRecommendationResponse,
)
from app.services.hardware import detect_hardware
from app.services.provider import ModelProviderRouter, ProviderError, get_router
from app.services.tier import recommend_tier

router = APIRouter(prefix="/setup", tags=["setup"])

OLLAMA_BASE_URL = "http://localhost:11434"
CONNECTION_TEST_TIMEOUT_SECONDS = 5.0

_PROVIDER_TEST_ENDPOINT = {
    "openai": "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
    "google": "https://generativelanguage.googleapis.com/v1beta/models",
    "groq": "https://api.groq.com/openai/v1/models",
}

_PROVIDER_AUTH_HEADER = {
    "openai": lambda key: {"Authorization": f"Bearer {key}"},
    "anthropic": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"},
    "google": lambda key: {},  # Google uses ?key= query param instead
    "groq": lambda key: {"Authorization": f"Bearer {key}"},
}


class ConfigureTierRequest(BaseModel):
    tier: TierOverrideRequest


class ConfigureTierResponse(BaseModel):
    tier: str
    model_plan: ModelPlanResponse


class DownloadModelsRequest(BaseModel):
    models: list[str]


class StoreApiKeyRequest(BaseModel):
    provider: str
    key: str
    base_url: str | None = None


class StoreApiKeyResponse(BaseModel):
    provider: str
    status: str


class TestConnectionRequest(BaseModel):
    provider: str
    key: str | None = None  # test an unsaved key, or omit to test the stored one
    base_url: str | None = None


class TestConnectionResponse(BaseModel):
    provider: str
    success: bool
    latency_ms: float | None
    models_available: int | None
    error: str | None = None


class SmokeTestResponse(BaseModel):
    success: bool
    latency_ms: float | None
    sample_output: str | None
    error: str | None = None


@router.post("/detect-hardware", response_model=HardwareProfileResponse)
def detect_hardware_step() -> HardwareProfileResponse:
    return HardwareProfileResponse.from_dataclass(detect_hardware())


@router.post("/recommend-tier", response_model=TierRecommendationResponse)
def recommend_tier_step() -> TierRecommendationResponse:
    profile = detect_hardware()
    return TierRecommendationResponse.from_dataclass(recommend_tier(profile))


@router.post("/configure-tier", response_model=ConfigureTierResponse)
def configure_tier_step(
    body: ConfigureTierRequest,
    db: DBSession = Depends(get_db),
    provider_router: ModelProviderRouter = Depends(get_router),
) -> ConfigureTierResponse:
    tier = body.tier.tier
    profile = detect_hardware()
    recommendation = recommend_tier(profile)

    if tier not in recommendation.available_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Tier '{tier.value}' is not available on this hardware.",
        )

    row = db.get(AppSettings, TIER_OVERRIDE_KEY)
    if row is None:
        db.add(AppSettings(key=TIER_OVERRIDE_KEY, value=tier.value))
    else:
        row.value = tier.value
    db.commit()

    provider_router.set_tier(tier)

    return ConfigureTierResponse(
        tier=tier.value,
        model_plan=ModelPlanResponse.from_dataclass(provider_router.model_plan),
    )


@router.post("/download-models")
async def download_models_step(body: DownloadModelsRequest) -> StreamingResponse:
    """SSE stream of download progress. Proxies Ollama's own `/api/pull`
    streaming NDJSON progress into `text/event-stream` frames the frontend
    can consume with `EventSource`/`fetch` + a reader."""

    async def event_stream():
        profile = detect_hardware()
        if not profile.ollama_available:
            yield _sse_event({"model": None, "status": "skipped", "detail": "Ollama not running"})
            return

        async with httpx.AsyncClient(timeout=None) as client:
            for model in body.models:
                yield _sse_event({"model": model, "status": "starting"})
                try:
                    async with client.stream(
                        "POST", f"{OLLAMA_BASE_URL}/api/pull", json={"name": model}
                    ) as resp:
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            yield _sse_event({"model": model, "raw": line})
                except httpx.HTTPError as err:
                    yield _sse_event({"model": model, "status": "error", "detail": str(err)})
                    continue
                yield _sse_event({"model": model, "status": "complete"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse_event(payload: dict) -> str:
    import json

    return f"data: {json.dumps(payload)}\n\n"


@router.post("/store-api-key", response_model=StoreApiKeyResponse)
def store_api_key_step(
    body: StoreApiKeyRequest,
    provider_router: ModelProviderRouter = Depends(get_router),
) -> StoreApiKeyResponse:
    try:
        provider_router.set_api_key(body.provider, body.key, base_url=body.base_url)
    except ProviderError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return StoreApiKeyResponse(provider=body.provider, status="stored")


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection_step(
    body: TestConnectionRequest,
    provider_router: ModelProviderRouter = Depends(get_router),
) -> TestConnectionResponse:
    provider = body.provider

    if provider == "custom":
        base_url = body.base_url
        if not base_url:
            return TestConnectionResponse(
                provider=provider,
                success=False,
                latency_ms=None,
                models_available=None,
                error="base_url is required for the custom provider",
            )
        url = base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {body.key}"} if body.key else {}
    else:
        if provider not in _PROVIDER_TEST_ENDPOINT:
            return TestConnectionResponse(
                provider=provider,
                success=False,
                latency_ms=None,
                models_available=None,
                error=f"Unknown provider: {provider}",
            )
        key = body.key or provider_router.get_api_key(provider)
        if not key:
            return TestConnectionResponse(
                provider=provider,
                success=False,
                latency_ms=None,
                models_available=None,
                error="No API key provided or stored for this provider",
            )
        url = _PROVIDER_TEST_ENDPOINT[provider]
        if provider == "google":
            url = f"{url}?key={key}"
        headers = _PROVIDER_AUTH_HEADER[provider](key)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=CONNECTION_TEST_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, headers=headers)
        latency_ms = round((time.monotonic() - start) * 1000, 1)

        if resp.status_code != 200:
            return TestConnectionResponse(
                provider=provider,
                success=False,
                latency_ms=latency_ms,
                models_available=None,
                error=f"HTTP {resp.status_code}",
            )

        data = resp.json()
        models = data.get("data") or data.get("models") or []
        return TestConnectionResponse(
            provider=provider, success=True, latency_ms=latency_ms, models_available=len(models)
        )
    except httpx.HTTPError as err:
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return TestConnectionResponse(
            provider=provider,
            success=False,
            latency_ms=latency_ms,
            models_available=None,
            error=str(err),
        )


@router.post("/run-smoke-test", response_model=SmokeTestResponse)
async def run_smoke_test_step(
    provider_router: ModelProviderRouter = Depends(get_router),
) -> SmokeTestResponse:
    """Sends one trivial chat completion through the currently configured
    tier + provider to confirm the whole pipeline actually works end to end,
    not just that a key looks well-formed."""
    start = time.monotonic()
    try:
        output = await provider_router.chat(
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            stream=False,
        )
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return SmokeTestResponse(success=True, latency_ms=latency_ms, sample_output=str(output))
    except ProviderError as err:
        return SmokeTestResponse(success=False, latency_ms=None, sample_output=None, error=str(err))
    except Exception as err:  # noqa: BLE001 — surface any provider/network failure to the wizard
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return SmokeTestResponse(
            success=False, latency_ms=latency_ms, sample_output=None, error=str(err)
        )
