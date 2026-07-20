import { useCallback, useEffect, useState } from "react";

import type { PoiseAPI } from "../lib/api";
import { deleteApiKey, isTauri, listConfiguredProviders, storeApiKey } from "../lib/ipc";
import type {
  CostEstimate,
  HardwareProfile,
  HardwareTier,
  ProviderStatus,
  SmokeTestResult,
  TestConnectionResult,
  TierRecommendation,
} from "../lib/types";

interface UseHardwareSettingsResult {
  profile: HardwareProfile | null;
  tier: TierRecommendation | null;
  providerStatus: ProviderStatus | null;
  costEstimate: CostEstimate | null;
  configuredProviders: string[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  overrideTier: (tier: HardwareTier) => Promise<void>;
  storeKey: (provider: string, key: string, baseUrl?: string) => Promise<void>;
  deleteKey: (provider: string) => Promise<void>;
  testConnection: (
    provider: string,
    key?: string,
    baseUrl?: string
  ) => Promise<TestConnectionResult>;
  runSmokeTest: () => Promise<SmokeTestResult>;
  setCostCap: (softCapTokens: number, softCapUsd: number) => Promise<void>;
}

/** Powers the Settings page's hardware/provider/cost sections. Reads all
 * four pieces of state in parallel and re-fetches after any action that
 * could change one of them (tier override, key store/delete). */
export function useHardwareSettings(api: PoiseAPI | null): UseHardwareSettingsResult {
  const [profile, setProfile] = useState<HardwareProfile | null>(null);
  const [tier, setTierState] = useState<TierRecommendation | null>(null);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!api) return;
    setLoading(true);
    setError(null);
    try {
      const [profileRes, tierRes, statusRes, costRes, configuredRes] = await Promise.all([
        api.getHardwareProfile(),
        api.getTier(),
        api.getProviderStatus(),
        api.getCostEstimate(),
        isTauri ? listConfiguredProviders() : Promise.resolve<string[]>([]),
      ]);
      setProfile(profileRes);
      setTierState(tierRes);
      setProviderStatus(statusRes);
      setCostEstimate(costRes);
      setConfiguredProviders(configuredRes);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const overrideTier = useCallback(
    async (nextTier: HardwareTier) => {
      if (!api) return;
      const rec = await api.setTier(nextTier);
      setTierState(rec);
      await refresh();
    },
    [api, refresh]
  );

  const storeKey = useCallback(
    async (provider: string, key: string, baseUrl?: string) => {
      await storeApiKey(provider, key, baseUrl);
      await refresh();
    },
    [refresh]
  );

  const deleteKey = useCallback(
    async (provider: string) => {
      await deleteApiKey(provider);
      await refresh();
    },
    [refresh]
  );

  const testConnection = useCallback(
    async (provider: string, key?: string, baseUrl?: string) => {
      if (!api) throw new Error("Sidecar not connected yet");
      return api.testConnection(provider, key, baseUrl);
    },
    [api]
  );

  const runSmokeTest = useCallback(async () => {
    if (!api) throw new Error("Sidecar not connected yet");
    return api.runSmokeTest();
  }, [api]);

  const setCostCap = useCallback(
    async (softCapTokens: number, softCapUsd: number) => {
      if (!api) return;
      const estimate = await api.setCostCap(softCapTokens, softCapUsd);
      setCostEstimate(estimate);
    },
    [api]
  );

  return {
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
  };
}
