// frontend/src/components/wizard/steps/CompleteStep.tsx
import { motion } from "framer-motion";
import type { StepProps } from "../FirstRunWizard";
import { useReducedMotion } from "../../../hooks/useReducedMotion";

export function CompleteStep({ onNext }: StepProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className="wizard-step wizard-step--centered">
      <motion.div
        className="wizard-complete-check"
        initial={prefersReducedMotion ? false : { scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 15 }}
        aria-hidden="true"
      >
        ✓
      </motion.div>
      <h1>You're ready!</h1>
      <p className="wizard-step__subtitle">
        Setup's done. Head to the Dashboard to start your first real practice session — you can revisit
        any of these steps later from Settings.
      </p>
      <button type="button" className="wizard-btn wizard-btn--primary" onClick={onNext} autoFocus>
        Go to Dashboard
      </button>
    </div>
  );
}
