import { useEffect, useState } from "react";
import type { PoiseAPI } from "../lib/api";
import type { SidecarStatus, TierRecommendation } from "../lib/types";

interface StatusBarProps {
  sidecarStatus: SidecarStatus | null;
  api?: PoiseAPI | null;
}

const STATUS_LABEL: Record<SidecarStatus["status"], string> = {
  starting: "Backend: Starting\u2026",
  healthy: "Backend: Connected",
  unhealthy: "Backend: Unhealthy",
  stopped: "Backend: Stopped",
};

export function StatusBar({ sidecarStatus, api }: StatusBarProps) {
  const state = sidecarStatus?.status ?? "starting";
  const [tier, setTier] = useState<TierRecommendation | null>(null);

  useEffect(() => {
    if (api && state === "healthy") {
      api.getTier<TierRecommendation>().then(setTier).catch(() => {});
    }
  }, [api, state]);

  const tierLabel = tier?.recommended_tier 
    ? tier.recommended_tier.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")
    : "Not configured";

  return (
    <footer className="status-bar" role="status">
      <div className={`status-bar__indicator status-bar__indicator--${state}`}>
        <span className="status-bar__dot" aria-hidden="true" />
        {STATUS_LABEL[state]}
      </div>

      <div className="status-bar__tier-badge">Hardware tier: {tierLabel}</div>
    </footer>
  );
}
