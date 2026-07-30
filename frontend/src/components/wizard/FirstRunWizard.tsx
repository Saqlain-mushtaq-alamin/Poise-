// frontend/src/components/wizard/FirstRunWizard.tsx
// Phase 9.1 — First-Run Wizard
//
// Merge notes:
// - Reads/writes completion flag via `useFirstRunFlag` (backed by the
//   Settings store from Phase 1 — swap the TODO marked calls for your
//   real settings API if the key name differs).
// - Re-entrant: Settings > "Redo setup" can mount this same component.
// - All step components live in ./steps and are intentionally dumb —
//   they take `onNext` / `onBack` / `state` / `setState` props only, so
//   later phases can unit test them with mock data per contracts/mocks.

import { useCallback, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { WizardProgress } from "./WizardProgress";
import { WIZARD_STEPS, initialWizardState, type WizardState, type WizardStepId } from "./wizard.types";
import { useReducedMotion } from "../../hooks/useReducedMotion";

import { WelcomeStep } from "./steps/WelcomeStep";
import { HardwareScanStep } from "./steps/HardwareScanStep";
import { TierConfirmStep } from "./steps/TierConfirmStep";
import { ModelDownloadStep } from "./steps/ModelDownloadStep";
import { ApiKeySetupStep } from "./steps/ApiKeySetupStep";
import { AudioCheckStep } from "./steps/AudioCheckStep";
import { CameraCheckStep } from "./steps/CameraCheckStep";
import { QuickDemoStep } from "./steps/QuickDemoStep";
import { CompleteStep } from "./steps/CompleteStep";

import "../../styles/wizard.css";

export interface FirstRunWizardProps {
  /** Called when the user finishes or explicitly skips setup. */
  onFinish: (state: WizardState) => void;
  /** Reopening from Settings ("Complete setup" reminder / "Redo setup"). */
  startAtStep?: WizardStepId;
}

const STEP_COMPONENTS: Record<WizardStepId, React.ComponentType<StepProps>> = {
  welcome: WelcomeStep,
  "hardware-scan": HardwareScanStep,
  "tier-confirm": TierConfirmStep,
  "model-download": ModelDownloadStep,
  "api-key-setup": ApiKeySetupStep,
  "audio-check": AudioCheckStep,
  "camera-check": CameraCheckStep,
  "quick-demo": QuickDemoStep,
  complete: CompleteStep,
};

export interface StepProps {
  state: WizardState;
  setState: React.Dispatch<React.SetStateAction<WizardState>>;
  onNext: () => void;
  onBack: () => void;
  onSkip?: () => void;
  isLast: boolean;
}

export function FirstRunWizard({ onFinish, startAtStep }: FirstRunWizardProps) {
  const prefersReducedMotion = useReducedMotion();
  const [state, setState] = useState<WizardState>(initialWizardState);

  // Filter steps by tier once it's known; before that, show the full list
  // so the progress bar doesn't jump around mid-flow.
  const visibleSteps = useMemo(() => {
    return WIZARD_STEPS.filter((s) => {
      if (!s.showFor) return true;
      if (!state.selectedTier) return true;
      return s.showFor.includes(state.selectedTier);
    });
  }, [state.selectedTier]);

  const startIndex = startAtStep
    ? Math.max(0, visibleSteps.findIndex((s) => s.id === startAtStep))
    : 0;
  const [currentIndex, setCurrentIndex] = useState(startIndex);

  const currentStep = visibleSteps[currentIndex];
  const isLast = currentIndex === visibleSteps.length - 1;

  const goNext = useCallback(() => {
    if (isLast) {
      onFinish(state);
      return;
    }
    setCurrentIndex((i) => Math.min(i + 1, visibleSteps.length - 1));
  }, [isLast, onFinish, state, visibleSteps.length]);

  const goBack = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

  const skipSetup = useCallback(() => {
    // Persist a "setup incomplete" flag so a reminder banner can surface
    // on the Dashboard until the user re-enters the wizard from Settings.
    // TODO(merge): replace with your real settings write, e.g.
    //   await settingsApi.set("firstRunCompleted", false);
    onFinish(state);
  }, [onFinish, state]);

  const StepComponent = STEP_COMPONENTS[currentStep.id];

  return (
    <div className="wizard" role="dialog" aria-modal="true" aria-label="First-time setup">
      <WizardProgress steps={visibleSteps} currentIndex={currentIndex} />

      <div className="wizard__body">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={currentStep.id}
            initial={prefersReducedMotion ? false : { opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={prefersReducedMotion ? undefined : { opacity: 0, x: -24 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.22, ease: "easeOut" }}
            className="wizard__step"
          >
            <StepComponent
              state={state}
              setState={setState}
              onNext={goNext}
              onBack={goBack}
              onSkip={currentStep.id !== "complete" ? skipSetup : undefined}
              isLast={isLast}
            />
          </motion.div>
        </AnimatePresence>
      </div>

      {currentStep.id !== "welcome" && currentStep.id !== "complete" && (
        <div className="wizard__footer">
          <button type="button" className="wizard__link-btn" onClick={goBack} disabled={currentIndex === 0}>
            Back
          </button>
          <button type="button" className="wizard__link-btn wizard__link-btn--muted" onClick={skipSetup}>
            Complete setup later
          </button>
        </div>
      )}
    </div>
  );
}
