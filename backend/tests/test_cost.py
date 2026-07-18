"""Cost/token tracking accuracy against known token counts."""

from __future__ import annotations

from app.services.cost import DEFAULT_SOFT_CAP_TOKENS, DEFAULT_SOFT_CAP_USD, TokenTracker


def test_starts_at_zero():
    tracker = TokenTracker()
    estimate = tracker.estimate()
    assert estimate.total_tokens == 0
    assert estimate.estimated_cost_usd == 0.0
    assert estimate.cap_warning is False


def test_accumulates_across_multiple_calls_same_model():
    tracker = TokenTracker()
    tracker.add("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
    tracker.add("gpt-4o-mini", prompt_tokens=200, completion_tokens=75)

    estimate = tracker.estimate()
    assert estimate.input_tokens == 300
    assert estimate.output_tokens == 125
    assert estimate.total_tokens == 425


def test_accumulates_across_different_models():
    tracker = TokenTracker()
    tracker.add("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    tracker.add("gpt-4o", prompt_tokens=2000, completion_tokens=1000)

    estimate = tracker.estimate()
    assert estimate.total_tokens == 4500


def test_fallback_pricing_used_when_litellm_unavailable(monkeypatch):
    tracker = TokenTracker()
    tracker.add("gpt-4o-mini", prompt_tokens=1000, completion_tokens=1000)

    # gpt-4o-mini fallback pricing: 0.00015 / 1k input, 0.0006 / 1k output
    expected = (1000 / 1000) * 0.00015 + (1000 / 1000) * 0.0006

    # Force the litellm cost lookup to fail so the fallback table is used.
    import app.services.cost as cost_module

    original_cost_for_model = cost_module.TokenTracker._cost_for_model

    def _force_fallback(self, model, usage):
        try:
            import litellm  # noqa: F401

            raise RuntimeError("simulate litellm not resolving this model")
        except RuntimeError:
            input_rate, output_rate = cost_module._FALLBACK_PRICING_PER_1K.get(model, (0.0, 0.0))
            return (usage.prompt_tokens / 1000) * input_rate + (
                usage.completion_tokens / 1000
            ) * output_rate

    monkeypatch.setattr(cost_module.TokenTracker, "_cost_for_model", _force_fallback)

    estimate = tracker.estimate()
    assert abs(estimate.estimated_cost_usd - round(expected, 4)) < 1e-6

    monkeypatch.setattr(cost_module.TokenTracker, "_cost_for_model", original_cost_for_model)


def test_cap_warning_fires_on_token_threshold():
    tracker = TokenTracker(soft_cap_tokens=1000, soft_cap_usd=999.0)
    tracker.add("local/model", prompt_tokens=600, completion_tokens=500)

    estimate = tracker.estimate()
    assert estimate.total_tokens == 1100
    assert estimate.cap_warning is True


def test_cap_warning_does_not_fire_below_threshold():
    tracker = TokenTracker(soft_cap_tokens=1000, soft_cap_usd=999.0)
    tracker.add("local/model", prompt_tokens=100, completion_tokens=100)

    estimate = tracker.estimate()
    assert estimate.cap_warning is False


def test_cap_warning_fires_on_cost_threshold_even_under_token_cap():
    tracker = TokenTracker(soft_cap_tokens=1_000_000, soft_cap_usd=0.01)
    tracker.add("gpt-4o", prompt_tokens=1000, completion_tokens=1000)  # ~$0.0125 by fallback

    estimate = tracker.estimate()
    assert estimate.cap_warning is True


def test_defaults_match_spec():
    assert DEFAULT_SOFT_CAP_TOKENS == 50_000
    assert DEFAULT_SOFT_CAP_USD == 2.0


def test_add_from_response_usage_handles_dict_shape():
    tracker = TokenTracker()
    tracker.add_from_response_usage("gpt-4o-mini", {"prompt_tokens": 10, "completion_tokens": 20})
    estimate = tracker.estimate()
    assert estimate.input_tokens == 10
    assert estimate.output_tokens == 20


def test_add_from_response_usage_handles_object_shape():
    class Usage:
        prompt_tokens = 5
        completion_tokens = 15

    tracker = TokenTracker()
    tracker.add_from_response_usage("gpt-4o-mini", Usage())
    estimate = tracker.estimate()
    assert estimate.input_tokens == 5
    assert estimate.output_tokens == 15


def test_add_from_response_usage_handles_none():
    tracker = TokenTracker()
    tracker.add_from_response_usage("gpt-4o-mini", None)
    assert tracker.estimate().total_tokens == 0


def test_reset_clears_usage():
    tracker = TokenTracker()
    tracker.add("gpt-4o-mini", 100, 100)
    tracker.reset()
    assert tracker.estimate().total_tokens == 0
