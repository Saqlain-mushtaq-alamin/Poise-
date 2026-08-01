// frontend/src/components/wizard/steps/TierConfirmStep.tsx
import type { StepProps } from "../FirstRunWizard";
import type { HardwareTier } from "../wizard.types";

const TIER_COPY: Record<HardwareTier, { title: string; blurb: string }> = {
  cloud: {
    title: "Cloud Assist",
    blurb: "Uses your own API key (BYOK) for the model provider. Fastest to start, needs no downloads.",
  },
  "local-lite": {
    title: "Local Lite",
    blurb: "Runs a small model on your CPU/GPU. Fully offline, lower resource use, good for quick practice.",
  },
  "local-full": {
    title: "Local Full",
    blurb: "Runs the full model set on your GPU. Fully offline, best quality, needs more VRAM and disk space.",
  },
};

export function TierConfirmStep({ state, setState, onNext, onSkip }: StepProps) {
  const selected = state.selectedTier ?? "cloud";

  return (
    <div className="wizard-step">
      <h1>Confirm your tier</h1>
      <p className="wizard-step__subtitle">
        {state.hardware
          ? `Based on your hardware, we recommend ${TIER_COPY[state.hardware.recommendedTier].title}. You can change this any time in Settings.`
          : "Pick the tier that fits how you want to run Poise."}
      </p>

      <div className="wizard-tier-options" role="radiogroup" aria-label="Choose a tier">
        {(Object.keys(TIER_COPY) as HardwareTier[]).map((tier) => (
          <label
            key={tier}
            className={`wizard-tier-card ${selected === tier ? "wizard-tier-card--selected" : ""}`}
          >
            <input
              type="radio"
              name="tier"
              value={tier}
              checked={selected === tier}
              onChange={() => setState((s) => ({ ...s, selectedTier: tier }))}
            />
            <span className="wizard-tier-card__title">{TIER_COPY[tier].title}</span>
            <span className="wizard-tier-card__blurb">{TIER_COPY[tier].blurb}</span>
            {state.hardware?.recommendedTier === tier && (
              <span className="wizard-tier-card__badge">Recommended</span>
            )}
          </label>
        ))}
      </div>

      <div className="wizard-step__actions">
        <button type="button" className="wizard-btn wizard-btn--primary" onClick={onNext}>
          Continue
        </button>
        {onSkip && (
          <button type="button" className="wizard__link-btn" onClick={onSkip}>
            Skip for now
          </button>
        )}
      </div>
    </div>
  );
}
