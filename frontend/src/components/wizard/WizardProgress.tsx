// frontend/src/components/wizard/WizardProgress.tsx
import { motion } from "framer-motion";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import type { WizardStepMeta } from "./wizard.types";

interface WizardProgressProps {
  steps: WizardStepMeta[];
  currentIndex: number;
}

export function WizardProgress({ steps, currentIndex }: WizardProgressProps) {
  const prefersReducedMotion = useReducedMotion();
  const total = steps.length;
  const step = currentIndex + 1;
  const pct = Math.round((step / total) * 100);

  return (
    <div
      className="wizard-progress"
      role="progressbar"
      aria-valuenow={step}
      aria-valuemin={1}
      aria-valuemax={total}
      aria-label={`Setup step ${step} of ${total}: ${steps[currentIndex]?.label}`}
    >
      <div className="wizard-progress__track">
        <motion.div
          className="wizard-progress__fill"
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }}
        />
      </div>
      <span className="wizard-progress__label">
        Step {step} of {total} — {steps[currentIndex]?.label}
      </span>
    </div>
  );
}
