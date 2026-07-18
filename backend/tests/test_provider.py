"""ModelProviderRouter: role resolution, tier switching, BYOK key handling,
and cost tracking — all with litellm mocked out (no real network calls)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.provider import (
    ModelProviderRouter,
    ModelRole,
    ProviderError,
)
from app.services.tier import HardwareTier


def test_reasoning_model_resolves_per_tier():
    router = ModelProviderRouter(tier=HardwareTier.LOCAL_FULL)
    assert router._resolve_model(ModelRole.REASONING) == router.model_plan.llm

    router.set_tier(HardwareTier.CLOUD_ASSIST)
    assert router._resolve_model(ModelRole.REASONING) == "gpt-4o-mini"


def test_pronunciation_is_always_local_regardless_of_tier():
    router = ModelProviderRouter(tier=HardwareTier.CLOUD_ASSIST)
    assert router._resolve_model(ModelRole.PRONUNCIATION) == "wav2vec2"


def test_vision_role_raises_on_local_lite_which_has_no_vlm():
    router = ModelProviderRouter(tier=HardwareTier.LOCAL_LITE)
    with pytest.raises(ProviderError):
        router._resolve_model(ModelRole.VISION)


def test_set_and_clear_api_key_updates_env(monkeypatch):
    router = ModelProviderRouter()
    router.set_api_key("openai", "sk-test-123")

    assert router.has_key("openai")
    assert router.get_api_key("openai") == "sk-test-123"
    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-test-123"

    router.clear_api_key("openai")
    assert not router.has_key("openai")
    assert "OPENAI_API_KEY" not in os.environ


def test_set_api_key_rejects_unknown_provider():
    router = ModelProviderRouter()
    with pytest.raises(ProviderError):
        router.set_api_key("not-a-real-provider", "whatever")


def test_chat_raises_without_key_on_cloud_assist():
    router = ModelProviderRouter(tier=HardwareTier.CLOUD_ASSIST)

    import asyncio

    with pytest.raises(ProviderError):
        asyncio.run(router.chat(messages=[{"role": "user", "content": "hi"}]))


@pytest.mark.asyncio
async def test_chat_tracks_tokens_from_litellm_response():
    router = ModelProviderRouter(tier=HardwareTier.LOCAL_FULL)

    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ready"))],
        usage={"prompt_tokens": 12, "completion_tokens": 3},
    )

    with patch("litellm.acompletion", new=AsyncMock(return_value=fake_response)) as mock_call:
        result = await router.chat(messages=[{"role": "user", "content": "hi"}])

    assert result == "ready"
    mock_call.assert_awaited_once()
    called_model = mock_call.call_args.kwargs["model"]
    assert called_model == f"ollama/{router.model_plan.llm}"

    estimate = router.get_cost_estimate()
    assert estimate.input_tokens == 12
    assert estimate.output_tokens == 3


@pytest.mark.asyncio
async def test_chat_routes_directly_to_cloud_model_name():
    router = ModelProviderRouter(tier=HardwareTier.CLOUD_ASSIST)
    router.set_api_key("openai", "sk-test")

    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
        usage={"prompt_tokens": 5, "completion_tokens": 1},
    )

    with patch("litellm.acompletion", new=AsyncMock(return_value=fake_response)) as mock_call:
        await router.chat(messages=[{"role": "user", "content": "hi"}])

    assert mock_call.call_args.kwargs["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_embed_tracks_tokens():
    router = ModelProviderRouter(tier=HardwareTier.LOCAL_FULL)

    fake_response = SimpleNamespace(
        data=[{"embedding": [0.1, 0.2, 0.3]}],
        usage={"prompt_tokens": 4, "completion_tokens": 0},
    )

    with patch("litellm.aembedding", new=AsyncMock(return_value=fake_response)):
        vector = await router.embed("some text")

    assert vector == [0.1, 0.2, 0.3]
    assert router.get_cost_estimate().input_tokens == 4


def test_status_reflects_tier_and_configured_providers():
    router = ModelProviderRouter(tier=HardwareTier.LOCAL_LITE)
    router.set_api_key("groq", "gsk_test")

    status = router.status(ollama_reachable=True)
    assert status.tier == HardwareTier.LOCAL_LITE
    assert status.configured_providers == ["groq"]
    assert status.ollama_reachable is True
