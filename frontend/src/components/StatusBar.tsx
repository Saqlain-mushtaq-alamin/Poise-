import type { SidecarStatus } from "../lib/types";

interface StatusBarProps {
  sidecarStatus: SidecarStatus | null;
}

const STATUS_LABEL: Record<SidecarStatus["status"], string> = {
  starting: "Backend: Starting\u2026",
  healthy: "Backend: Connected",
  unhealthy: "Backend: Unhealthy",
  stopped: "Backend: Stopped",
};

export function StatusBar({ sidecarStatus }: StatusBarProps) {
  const state = sidecarStatus?.status ?? "starting";

  return (
    <footer className="status-bar" role="status">
      <div className={`status-bar__indicator status-bar__indicator--${state}`}>
        <span className="status-bar__dot" aria-hidden="true" />
        {STATUS_LABEL[state]}
      </div>

      {/* Populated by Phase 2 (Hardware Detection). Shows a static
          "Not configured" badge until then per the Phase 1 spec. */}
      <div className="status-bar__tier-badge">Hardware tier: Not configured</div>
    </footer>
  );
}
