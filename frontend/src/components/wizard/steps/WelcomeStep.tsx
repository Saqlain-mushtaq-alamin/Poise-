// frontend/src/components/wizard/steps/WelcomeStep.tsx
import { motion } from "framer-motion";
import type { StepProps } from "../FirstRunWizard";
import { useReducedMotion } from "../../../hooks/useReducedMotion";

export function WelcomeStep({ onNext, onSkip }: StepProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="wizard-step wizard-step--centered">
      <motion.div
        className="wizard-logo"
        initial={prefersReducedMotion ? false : { scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        aria-hidden="true"
      >
        {/* TODO(merge): swap for the real <PoiseLogo /> asset component */}
        <div className="wizard-logo__mark">P</div>
      </motion.div>

      <h1>Let's set you up</h1>
      <p className="wizard-step__subtitle">
        A couple of quick checks and we'll have Poise tuned to your machine and ready for your first
        practice session.
      </p>

      <div className="wizard-step__actions">
        <button type="button" className="wizard-btn wizard-btn--primary" onClick={onNext} autoFocus>
          Get started
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
