"""Token/cost tracking for BYOK cloud sessions.

Local tiers cost nothing per-token, but we still track token counts for
them (useful context in reports later); only cloud tiers turn those tokens
into a dollar estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SOFT_CAP_TOKENS = 50_000
DEFAULT_SOFT_CAP_USD = 2.0

# Minimal built-in price table (USD per 1K tokens) as a fallback for models
# LiteLLM's cost database doesn't recognize (e.g. local Ollama models,
# which are free). Real cloud pricing should come from
# `litellm.cost_per_token` when available — see ModelProviderRouter.
_FALLBACK_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    # model: (input_usd_per_1k, output_usd_per_1k)
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini-tts": (0.0006, 0.0006),
}


@dataclass
class CostEstimate:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    soft_cap_tokens: int
    soft_cap_usd: float
    cap_warning: bool


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


class TokenTracker:
    """Accumulates token usage for a single session and estimates cost.

    One instance lives per active session inside `ModelProviderRouter`; it
    is intentionally not persisted — Phase 8 (Scoring & Progress) is
    responsible for writing a final cost summary into session history once
    a session ends.
    """

    def __init__(
        self,
        soft_cap_tokens: int = DEFAULT_SOFT_CAP_TOKENS,
        soft_cap_usd: float = DEFAULT_SOFT_CAP_USD,
    ) -> None:
        self.soft_cap_tokens = soft_cap_tokens
        self.soft_cap_usd = soft_cap_usd
        self._usage_by_model: dict[str, _Usage] = {}

    def add(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        usage = self._usage_by_model.setdefault(model, _Usage())
        usage.prompt_tokens += max(prompt_tokens, 0)
        usage.completion_tokens += max(completion_tokens, 0)

    def add_from_response_usage(self, model: str, usage: object | None) -> None:
        """Convenience for LiteLLM/OpenAI-shaped `response.usage` objects
        (which may be a dict or an object with attributes, depending on
        provider)."""
        if usage is None:
            return
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", 0)
            completion = usage.get("completion_tokens", 0)
        else:
            prompt = getattr(usage, "prompt_tokens", 0)
            completion = getattr(usage, "completion_tokens", 0)
        self.add(model, prompt or 0, completion or 0)

    def _cost_for_model(self, model: str, usage: _Usage) -> float:
        try:
            import litellm

            input_cost, output_cost = litellm.cost_per_token(
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )
            return input_cost + output_cost
        except Exception:
            pass

        input_rate, output_rate = _FALLBACK_PRICING_PER_1K.get(model, (0.0, 0.0))
        return (usage.prompt_tokens / 1000) * input_rate + (
            usage.completion_tokens / 1000
        ) * output_rate

    def estimate(self) -> CostEstimate:
        input_tokens = sum(u.prompt_tokens for u in self._usage_by_model.values())
        output_tokens = sum(u.completion_tokens for u in self._usage_by_model.values())
        total_tokens = input_tokens + output_tokens
        total_cost = sum(
            self._cost_for_model(model, usage) for model, usage in self._usage_by_model.items()
        )

        cap_warning = total_tokens >= self.soft_cap_tokens or total_cost >= self.soft_cap_usd

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(total_cost, 4),
            soft_cap_tokens=self.soft_cap_tokens,
            soft_cap_usd=self.soft_cap_usd,
            cap_warning=cap_warning,
        )

    def reset(self) -> None:
        self._usage_by_model.clear()
