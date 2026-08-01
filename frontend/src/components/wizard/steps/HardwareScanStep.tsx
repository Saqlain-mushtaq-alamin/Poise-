// frontend/src/components/wizard/steps/HardwareScanStep.tsx
//
// Merge notes: this calls the Phase 2 "hardware" contract
// (contracts/api/hardware.yaml -> GET /hardware/scan). Swap `scanHardware`
// for your real `lib/api.ts` client if the function name differs.
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import type { StepProps } from "../FirstRunWizard";
import type { HardwareScanResult } from "../wizard.types";
import { invokeSidecar } from "../../../lib/api";

async function scanHardware(): Promise<HardwareScanResult> {
  // TODO(merge): point this at the real Phase 2 endpoint, e.g.
  //   return invokeSidecar<HardwareScanResult>("GET", "/hardware/scan");
  return invokeSidecar<HardwareScanResult>("GET", "/hardware/scan");
}

export function HardwareScanStep({ state, setState, onNext, onSkip }: StepProps) {
  const [phase, setPhase] = useState<"scanning" | "done" | "error">("scanning");
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    let cancelled = false;
    scanHardware()
      .then((result) => {
        if (cancelled) return;
        setState((s) => ({ ...s, hardware: result, selectedTier: result.recommendedTier }));
        setPhase("done");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Hardware scan failed");
        setPhase("error");
      });

    return () => {
      cancelled = true;
    };
  }, [setState]);

  return (
    <div className="wizard-step wizard-step--centered">
      <h1>Scanning your hardware</h1>
      <p className="wizard-step__subtitle">
        We're checking your CPU, memory, and GPU to recommend the best tier — this only takes a moment.
      </p>

      {phase === "scanning" && (
        <div className="wizard-scan" role="status" aria-live="polite">
          <motion.div
            className="wizard-scan__spinner"
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.1, ease: "linear" }}
            aria-hidden="true"
          />
          <span>Detecting specs…</span>
        </div>
      )}

      {phase === "done" && state.hardware && (
        <div className="wizard-scan__result">
          <dl className="wizard-specs">
            <div>
              <dt>CPU</dt>
              <dd>{state.hardware.cpu}</dd>
            </div>
            <div>
              <dt>RAM</dt>
              <dd>{state.hardware.ramGb} GB</dd>
            </div>
            <div>
              <dt>GPU</dt>
              <dd>{state.hardware.gpu ?? "Not detected"}</dd>
            </div>
            {state.hardware.gpu && (
              <div>
                <dt>VRAM</dt>
                <dd>{state.hardware.vramGb ? `${state.hardware.vramGb} GB` : "Unknown"}</dd>
              </div>
            )}
          </dl>
          <button type="button" className="wizard-btn wizard-btn--primary" onClick={onNext} autoFocus>
            Continue
          </button>
        </div>
      )}

      {phase === "error" && (
        <div className="wizard-scan__result" role="alert">
          <p className="wizard-error-text">
            We couldn't complete an automatic scan ({error}). No problem — you can pick a tier manually
            on the next step.
          </p>
          <button
            type="button"
            className="wizard-btn wizard-btn--primary"
            onClick={() => {
              setState((s) => ({ ...s, hardware: null, selectedTier: "cloud" }));
              onNext();
            }}
          >
            Choose manually
          </button>
        </div>
      )}

      {onSkip && (
        <button type="button" className="wizard__link-btn" onClick={onSkip}>
          Skip for now
        </button>
      )}
    </div>
  );
}
