import * as Switch from "@radix-ui/react-switch";
import { useState } from "react";

import { ApiKeyManager } from "../components/settings/ApiKeyManager";
import { CostLimitSlider } from "../components/settings/CostLimitSlider";
import { HardwareTierCard } from "../components/settings/HardwareTierCard";
import { ModelConfigCard } from "../components/settings/ModelConfigCard";
import { useHardwareSettings } from "../hooks/useHardwareSettings";
import { useTheme } from "../hooks/useTheme";
import type { PoiseAPI } from "../lib/api";

interface SettingsProps {
  api: PoiseAPI | null;
}

export function Settings({ api }: SettingsProps) {
  const { theme, toggleTheme } = useTheme();
  const {
    profile,
    tier,
    providerStatus,
    costEstimate,
    configuredProviders,
    loading,
    error,
    refresh,
    overrideTier,
    storeKey,
    deleteKey,
    testConnection,
    runSmokeTest,
    setCostCap,
  } = useHardwareSettings(api);

  const [smokeTestResult, setSmokeTestResult] = useState<string | null>(null);
  const [smokeTestBusy, setSmokeTestBusy] = useState(false);

  async function handleSmokeTest() {
    setSmokeTestBusy(true);
    setSmokeTestResult(null);
    try {
      const result = await runSmokeTest();
      setSmokeTestResult(
        result.success
          ? `Success — "${result.sample_output}" in ${result.latency_ms}ms`
          : `Failed: ${result.error}`
      );
    } finally {
      setSmokeTestBusy(false);
    }
  }

  return (
    <div className="page">
      <h1>Settings</h1>

      <section className="settings__section">
        <h2>Appearance</h2>
        <label className="settings__row">
          <span>Dark theme</span>
          <Switch.Root
            className="switch"
            checked={theme === "dark"}
            onCheckedChange={toggleTheme}
            aria-label="Toggle dark theme"
          >
            <Switch.Thumb className="switch__thumb" />
          </Switch.Root>
        </label>
      </section>

      <section className="settings__section">
        <h2>Hardware &amp; model providers</h2>

        {error && <p className="settings-card__warning">{error}</p>}

        <HardwareTierCard
          profile={profile}
          tier={tier}
          loading={loading}
          onOverride={overrideTier}
          onRedetect={refresh}
        />

        <ApiKeyManager
          configuredProviders={configuredProviders}
          onStore={storeKey}
          onDelete={deleteKey}
          onTest={testConnection}
        />

        <ModelConfigCard modelPlan={providerStatus?.model_plan ?? null} />

        <CostLimitSlider costEstimate={costEstimate} onChange={setCostCap} />

        <div className="settings-card">
          <h3>Smoke test</h3>
          <p className="page__placeholder-note">
            Sends one trivial request through the active tier + provider to confirm everything
            actually works end to end.
          </p>
          <button type="button" onClick={handleSmokeTest} disabled={smokeTestBusy}>
            {smokeTestBusy ? "Running\u2026" : "Run smoke test"}
          </button>
          {smokeTestResult && <p className="settings-card__reason">{smokeTestResult}</p>}
        </div>
      </section>
    </div>
  );
}
