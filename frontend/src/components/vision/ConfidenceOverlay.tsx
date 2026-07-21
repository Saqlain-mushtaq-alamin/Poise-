import { useState } from "react";

interface ConfidenceOverlayProps {
  score: number; // 0-100
  eyeContactRatio: number; // 0-1
  expression: string;
  gestureAssessment?: string;
  visible: boolean;
  onToggleVisible: () => void;
}

function scoreColor(score: number): string {
  if (score >= 70) return "var(--color-accent-success)";
  if (score >= 40) return "var(--color-accent-warning)";
  return "var(--color-accent-danger)";
}

const RADIUS = 26;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function ConfidenceOverlay({
  score,
  eyeContactRatio,
  expression,
  gestureAssessment,
  visible,
  onToggleVisible,
}: ConfidenceOverlayProps) {
  const [minimized, setMinimized] = useState(false);

  if (!visible) {
    return (
      <button
        type="button"
        className="confidence-overlay__reopen"
        onClick={onToggleVisible}
        aria-label="Show confidence overlay"
      >
        Show confidence
      </button>
    );
  }

  const clampedScore = Math.max(0, Math.min(100, score));
  const offset = CIRCUMFERENCE * (1 - clampedScore / 100);
  const color = scoreColor(clampedScore);

  return (
    <div className={`confidence-overlay${minimized ? " confidence-overlay--minimized" : ""}`}>
      <div className="confidence-overlay__gauge-wrap">
        <svg width="64" height="64" viewBox="0 0 64 64" role="meter" aria-valuenow={clampedScore}>
          <circle cx="32" cy="32" r={RADIUS} fill="none" stroke="var(--color-surface)" strokeWidth="6" />
          <circle
            cx="32"
            cy="32"
            r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform="rotate(-90 32 32)"
            style={{ transition: "stroke-dashoffset 300ms ease, stroke 300ms ease" }}
          />
        </svg>
        <span className="confidence-overlay__score">{Math.round(clampedScore)}</span>
      </div>

      {!minimized && (
        <div className="confidence-overlay__indicators">
          <span title="Eye contact (30s rolling average)">
            {"\u{1F441}"} {Math.round(eyeContactRatio * 100)}%
          </span>
          <span title="Expression">
            {"\u{1F9E0}"} {expression}
          </span>
          {gestureAssessment && (
            <span title="Posture / gestures">
              {"\u{1F4D0}"} {gestureAssessment}
            </span>
          )}
        </div>
      )}

      <div className="confidence-overlay__controls">
        <button
          type="button"
          onClick={() => setMinimized((m) => !m)}
          aria-label={minimized ? "Expand confidence overlay" : "Minimize confidence overlay"}
        >
          {minimized ? "\u25B4" : "\u25BE"}
        </button>
        <button type="button" onClick={onToggleVisible} aria-label="Hide confidence overlay">
          {"\u00D7"}
        </button>
      </div>
    </div>
  );
}
