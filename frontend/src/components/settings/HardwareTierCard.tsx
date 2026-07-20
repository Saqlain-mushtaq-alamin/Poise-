import type { HardwareProfile, HardwareTier, TierRecommendation } from "../../lib/types";

const TIER_LABEL: Record<HardwareTier, string> = {
  local_full: "Local Full",
  local_lite: "Local Lite",
  cloud_assist: "Cloud Assist",
};

interface HardwareTierCardProps {
  profile: HardwareProfile | null;
  tier: TierRecommendation | null;
  loading: boolean;
  onOverride: (tier: HardwareTier) => void;
  onRedetect: () => void;
}

export function HardwareTierCard({
  profile,
  tier,
  loading,
  onOverride,
  onRedetect,
}: HardwareTierCardProps) {
  return (
    <div className="settings-card">
      <div className="settings-card__header">
        <h3>Hardware &amp; tier</h3>
        <button type="button" onClick={onRedetect} disabled={loading} className="settings-card__button">
          {loading ? "Detecting\u2026" : "Re-run detection"}
        </button>
      </div>

      {profile && (
        <dl className="settings-card__specs">
          <div>
            <dt>OS</dt>
            <dd>{profile.os}</dd>
          </div>
          <div>
            <dt>CPU</dt>
            <dd>
              {profile.cpu_name} ({profile.cpu_cores} cores)
            </dd>
          </div>
          <div>
            <dt>RAM</dt>
            <dd>
              {profile.ram_available_gb.toFixed(1)} / {profile.ram_total_gb.toFixed(1)} GB free
            </dd>
          </div>
          <div>
            <dt>GPU</dt>
            <dd>
              {profile.gpus.length === 0
                ? "None detected"
                : profile.gpus
                    .map((g) => `${g.name} (${(g.vram_available_mb / 1024).toFixed(1)}GB free)`)
                    .join(", ")}
            </dd>
          </div>
          <div>
            <dt>Docker</dt>
            <dd>{profile.docker_available ? "Available" : "Not detected"}</dd>
          </div>
          <div>
            <dt>Ollama</dt>
            <dd>{profile.ollama_available ? "Running" : "Not running"}</dd>
          </div>
        </dl>
      )}

      {tier && (
        <div className="settings-card__tier">
          <label htmlFor="tier-override">Active tier</label>
          <select
            id="tier-override"
            value={tier.recommended_tier}
            onChange={(e) => onOverride(e.target.value as HardwareTier)}
          >
            {tier.available_tiers.map((t) => (
              <option key={t} value={t}>
                {TIER_LABEL[t]}
              </option>
            ))}
          </select>
          <p className="settings-card__reason">{tier.reason}</p>
          {tier.warnings.map((warning) => (
            <p key={warning} className="settings-card__warning">
              {"\u26A0"} {warning}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
