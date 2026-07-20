import { useEffect, useState } from "react";

import type { CostEstimate } from "../../lib/types";

const MIN_TOKENS = 5_000;
const MAX_TOKENS = 200_000;
const STEP_TOKENS = 5_000;
// Rough $/token ratio derived from the spec's default (50K tokens ~= $2).
const USD_PER_TOKEN = 2.0 / 50_000;

interface CostLimitSliderProps {
  costEstimate: CostEstimate | null;
  onChange: (softCapTokens: number, softCapUsd: number) => void;
}

export function CostLimitSlider({ costEstimate, onChange }: CostLimitSliderProps) {
  const [tokens, setTokens] = useState(costEstimate?.soft_cap_tokens ?? 50_000);

  useEffect(() => {
    if (costEstimate) setTokens(costEstimate.soft_cap_tokens);
  }, [costEstimate]);

  const estimatedCap = Math.round(tokens * USD_PER_TOKEN * 100) / 100;

  function commit(nextTokens: number) {
    setTokens(nextTokens);
    onChange(nextTokens, Math.round(nextTokens * USD_PER_TOKEN * 100) / 100);
  }

  return (
    <div className="settings-card">
      <h3>Cost limits</h3>
      <p className="page__placeholder-note">
        Cloud Assist sessions warn you before crossing this cap. Local tiers are unaffected — they
        cost nothing per token.
      </p>

      <label className="cost-slider__row" htmlFor="cost-cap-slider">
        <span>
          {tokens.toLocaleString()} tokens (~${estimatedCap.toFixed(2)}) per session
        </span>
        <input
          id="cost-cap-slider"
          type="range"
          min={MIN_TOKENS}
          max={MAX_TOKENS}
          step={STEP_TOKENS}
          value={tokens}
          onChange={(e) => setTokens(Number(e.target.value))}
          onMouseUp={() => commit(tokens)}
          onTouchEnd={() => commit(tokens)}
          onKeyUp={() => commit(tokens)}
        />
      </label>

      {costEstimate && (
        <div className={`cost-slider__current${costEstimate.cap_warning ? " cost-slider__current--warning" : ""}`}>
          Current session: {costEstimate.total_tokens.toLocaleString()} tokens, $
          {costEstimate.estimated_cost_usd.toFixed(4)}
          {costEstimate.cap_warning && " — approaching your cap"}
        </div>
      )}
    </div>
  );
}
