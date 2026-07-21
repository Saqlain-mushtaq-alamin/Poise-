import { useEffect } from "react";

import type { CoachingTip } from "../../services/vision/confidenceCoach";

interface CoachingToastProps {
  tip: CoachingTip | null;
  onDismiss: () => void;
  autoDismissMs?: number;
}

const DEFAULT_AUTO_DISMISS_MS = 5000;

export function CoachingToast({
  tip,
  onDismiss,
  autoDismissMs = DEFAULT_AUTO_DISMISS_MS,
}: CoachingToastProps) {
  useEffect(() => {
    if (!tip) return;
    const timer = setTimeout(onDismiss, autoDismissMs);
    return () => clearTimeout(timer);
  }, [tip, onDismiss, autoDismissMs]);

  if (!tip) return null;

  return (
    <div
      className={`coaching-toast coaching-toast--${tip.severity}`}
      role="status"
      aria-live="polite"
    >
      <p className="coaching-toast__message">{tip.message}</p>
      {tip.exercise && <p className="coaching-toast__exercise">{tip.exercise}</p>}
    </div>
  );
}
