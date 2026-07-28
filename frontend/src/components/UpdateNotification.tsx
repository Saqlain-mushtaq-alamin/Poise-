// frontend/src/components/UpdateNotification.tsx
// Phase 9.4 — small toast-style banner driven by useAutoUpdater.
// Mount once near the app root (e.g. in Shell.tsx from Phase 1).
import { useAutoUpdater } from "../hooks/useAutoUpdater";

export function UpdateNotification() {
  const { state, installUpdate, restartToApply } = useAutoUpdater();

  if (state.phase === "idle" || state.phase === "checking" || state.phase === "none") return null;

  return (
    <div className="update-banner" role="status" aria-live="polite">
      {state.phase === "available" && (
        <>
          <span>Update {state.version} is available.</span>
          <button type="button" className="wizard-btn wizard-btn--secondary" onClick={installUpdate}>
            Download &amp; install
          </button>
        </>
      )}

      {state.phase === "downloading" && (
        <span>Downloading update… {state.progress}%</span>
      )}

      {state.phase === "ready" && (
        <>
          <span>Update installed — restart to apply.</span>
          <button type="button" className="wizard-btn wizard-btn--primary" onClick={restartToApply}>
            Restart now
          </button>
        </>
      )}

      {state.phase === "error" && (
        <span className="wizard-error-text">Update check failed: {state.error}</span>
      )}
    </div>
  );
}
