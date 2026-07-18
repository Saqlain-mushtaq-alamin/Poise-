"""Unified model provider router.

Downstream phases (4, 6, 7, 8) call `router.chat(...)` / `router.embed(...)`
without knowing or caring whether that resolves to a local Ollama model or
a cloud provider — that decision is made here, once, based on the current
hardware tier.

API keys are held in memory only. They arrive via `set_api_key()`, which
the Rust side calls (through the `/provider/keys/{provider}` endpoint) after
reading them out of the OS keychain — see src-tauri/src/keychain.rs. Nothing
in this module writes a key to disk, the database, or a log line.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.services.cost import CostEstimate, TokenTracker
from app.services.tier import HardwareTier, ModelPlan, model_plan_for

logger = logging.getLogger("poise.provider")

# Maps our provider identifiers to the environment variable LiteLLM/each
# SDK expects the API key under.
_PROVIDER_ENV_VAR = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}

SUPPORTED_PROVIDERS = tuple(_PROVIDER_ENV_VAR.keys()) + ("custom",)


class ModelRole(str, Enum):
    REASONING = "reasoning"
    VISION = "vision"
    EMBEDDING = "embedding"
    PRONUNCIATION = "pronunciation"  # wav2vec2 — always local, never routed


class ProviderError(RuntimeError):
    """Raised when a role has no usable model configured (e.g. Local Lite
    has no VLM, or Cloud Assist is selected with no key stored yet)."""


@dataclass
class ProviderStatus:
    tier: HardwareTier
    model_plan: ModelPlan
    configured_providers: list[str]
    ollama_reachable: bool


class ModelProviderRouter:
    def __init__(
        self,
        tier: HardwareTier = HardwareTier.CLOUD_ASSIST,
        token_tracker: TokenTracker | None = None,
    ) -> None:
        self._tier = tier
        self._model_plan = model_plan_for(tier)
        self._api_keys: dict[str, str] = {}
        self._custom_base_url: str | None = None
        self.token_tracker = token_tracker or TokenTracker()

    # ---- configuration ----

    def set_tier(self, tier: HardwareTier) -> None:
        self._tier = tier
        self._model_plan = model_plan_for(tier)

    @property
    def tier(self) -> HardwareTier:
        return self._tier

    @property
    def model_plan(self) -> ModelPlan:
        return self._model_plan

    def set_api_key(self, provider: str, key: str, base_url: str | None = None) -> None:
        """Store a key in memory for this process's lifetime and export it
        as the env var the underlying SDK looks for. Never logged."""
        if provider not in SUPPORTED_PROVIDERS:
            raise ProviderError(f"Unknown provider: {provider}")

        self._api_keys[provider] = key
        if provider == "custom":
            self._custom_base_url = base_url
            return

        import os

        os.environ[_PROVIDER_ENV_VAR[provider]] = key

    def clear_api_key(self, provider: str) -> None:
        self._api_keys.pop(provider, None)
        env_var = _PROVIDER_ENV_VAR.get(provider)
        if env_var:
            import os

            os.environ.pop(env_var, None)

    def has_key(self, provider: str) -> bool:
        return provider in self._api_keys

    def get_api_key(self, provider: str) -> str | None:
        return self._api_keys.get(provider)

    def configured_providers(self) -> list[str]:
        return sorted(self._api_keys.keys())

    def status(self, ollama_reachable: bool = False) -> ProviderStatus:
        return ProviderStatus(
            tier=self._tier,
            model_plan=self._model_plan,
            configured_providers=self.configured_providers(),
            ollama_reachable=ollama_reachable,
        )

    # ---- model resolution ----

    def _resolve_model(self, model_role: ModelRole) -> str:
        if model_role == ModelRole.PRONUNCIATION:
            # Always local regardless of tier — never sent to a cloud API.
            return "wav2vec2"

        plan = self._model_plan
        model = {
            ModelRole.REASONING: plan.llm,
            ModelRole.VISION: plan.vlm,
            ModelRole.EMBEDDING: plan.embedding,
        }[model_role]

        if model is None:
            raise ProviderError(
                f"No model configured for role={model_role.value} at tier={self._tier.value}"
            )
        return model

    def _is_cloud_model(self, model: str) -> bool:
        # Ollama-served models are addressed as "ollama/<name>" once we hand
        # them to LiteLLM; anything else here is a cloud model needing a key.
        return self._tier == HardwareTier.CLOUD_ASSIST

    def _litellm_model_name(self, model: str) -> str:
        if self._tier in (HardwareTier.LOCAL_FULL, HardwareTier.LOCAL_LITE):
            return f"ollama/{model}"
        return model

    # ---- calls ----

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model_role: ModelRole = ModelRole.REASONING,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | AsyncGenerator[str, None]:
        model = self._resolve_model(model_role)

        if self._is_cloud_model(model) and not self._api_keys:
            raise ProviderError("Cloud Assist tier selected but no API key is configured yet.")

        import litellm

        litellm_model = self._litellm_model_name(model)

        if stream:
            return self._stream_chat(litellm_model, model, messages, **kwargs)

        response = await litellm.acompletion(
            model=litellm_model, messages=messages, stream=False, **kwargs
        )
        usage = getattr(response, "usage", None)
        self.token_tracker.add_from_response_usage(model, usage)
        return response.choices[0].message.content

    async def _stream_chat(
        self, litellm_model: str, tracked_model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        import litellm

        response = await litellm.acompletion(
            model=litellm_model, messages=messages, stream=True, **kwargs
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                self.token_tracker.add_from_response_usage(tracked_model, usage)

    async def embed(self, text: str) -> list[float]:
        model = self._resolve_model(ModelRole.EMBEDDING)

        if self._is_cloud_model(model) and not self._api_keys:
            raise ProviderError("Cloud Assist tier selected but no API key is configured yet.")

        import litellm

        litellm_model = self._litellm_model_name(model)
        response = await litellm.aembedding(model=litellm_model, input=[text])
        usage = getattr(response, "usage", None)
        self.token_tracker.add_from_response_usage(model, usage)
        return response.data[0]["embedding"]

    def get_cost_estimate(self) -> CostEstimate:
        return self.token_tracker.estimate()


# Process-wide singleton. FastAPI dependency `get_router()` returns this so
# every request shares the same in-memory key store and token tally.
_router_instance = ModelProviderRouter()


def get_router() -> ModelProviderRouter:
    return _router_instance
