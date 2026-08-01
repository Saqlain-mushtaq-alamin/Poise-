// frontend/src/components/wizard/steps/ModelDownloadStep.tsx
//
// Merge notes: wires to Phase 2's model download endpoints. Assumes the
// sidecar exposes progress over Server-Sent Events or polling at
// GET /models/download/status — adjust `useModelDownloadProgress` to match
// whatever transport Phase 2 actually shipped with.
import { useEffect, useState } from "react";
import type { StepProps } from "../FirstRunWizard";
import { invokeSidecar } from "../../../lib/api";

interface ModelProgress {
  name: string;
  sizeMb: number;
  downloadedMb: number;
  status: "queued" | "downloading" | "done" | "failed";
  etaSeconds: number | null;
}

function useModelDownloadProgress(tier: string | null, enabled: boolean) {
  const [models, setModels] = useState<ModelProgress[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !tier) return;
    let cancelled = false;
    let interval: ReturnType<typeof setInterval>;

    invokeSidecar("POST", "/models/download/start", { tier }).catch((err) => {
      if (!cancelled) setError(err instanceof Error ? err.message : "Failed to start download");
    });

    interval = setInterval(async () => {
      try {
        const status = await invokeSidecar<ModelProgress[]>("GET", "/models/download/status");
        if (!cancelled) setModels(status);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch progress");
      }
    }, 1000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [tier, enabled]);

  return { models, error };
}

export function ModelDownloadStep({ state, setState, onNext, onSkip }: StepProps) {
  const { models, error } = useModelDownloadProgress(state.selectedTier, !state.modelsDownloaded);

  const allDone = models.length > 0 && models.every((m) => m.status === "done");
  const anyFailed = models.some((m) => m.status === "failed");

  useEffect(() => {
    if (allDone && !state.modelsDownloaded) {
      setState((s) => ({ ...s, modelsDownloaded: true }));
    }
  }, [allDone, setState, state.modelsDownloaded]);

  return (
    <div className="wizard-step">
      <h1>Downloading models</h1>
      <p className="wizard-step__subtitle">
        Grab a coffee — this runs in the background and resumes automatically if it's interrupted.
      </p>

      {error && <p className="wizard-error-text" role="alert">{error}</p>}

      <div className="wizard-download-list">
        {models.map((m) => {
          const pct = m.sizeMb > 0 ? Math.round((m.downloadedMb / m.sizeMb) * 100) : 0;
          return (
            <div className="wizard-download-item" key={m.name}>
              <div className="wizard-download-item__header">
                <span>{m.name}</span>
                <span>
                  {m.status === "done"
                    ? "Done"
                    : m.status === "failed"
                    ? "Failed — will retry"
                    : `${pct}% ${m.etaSeconds ? `(~${m.etaSeconds}s left)` : ""}`}
                </span>
              </div>
              <div className="wizard-download-item__track">
                <div
                  className={`wizard-download-item__fill ${m.status === "failed" ? "wizard-download-item__fill--error" : ""}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
        {models.length === 0 && !error && <p>Preparing download…</p>}
      </div>

      <div className="wizard-step__actions">
        <button
          type="button"
          className="wizard-btn wizard-btn--primary"
          onClick={onNext}
          disabled={!allDone && !anyFailed}
        >
          {allDone ? "Continue" : anyFailed ? "Continue anyway" : "Waiting for download…"}
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
