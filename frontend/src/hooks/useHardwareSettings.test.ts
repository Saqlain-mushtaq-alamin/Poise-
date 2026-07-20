import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PoiseAPI } from "../lib/api";
import * as ipc from "../lib/ipc";
import { useHardwareSettings } from "./useHardwareSettings";

function fakeApi(overrides: Partial<PoiseAPI> = {}): PoiseAPI {
  return {
    getHardwareProfile: vi.fn().mockResolvedValue({
      os: "linux",
      cpu_cores: 8,
      cpu_name: "Test CPU",
      ram_total_gb: 32,
      ram_available_gb: 20,
      gpus: [],
      docker_available: true,
      ollama_available: false,
      ollama_models: [],
    }),
    getTier: vi.fn().mockResolvedValue({
      recommended_tier: "cloud_assist",
      reason: "test reason",
      available_tiers: ["cloud_assist"],
      model_plan: { llm: "gpt-4o-mini", vlm: "gpt-4o", stt: "whisper-1", tts: "tts-1", embedding: "text-embedding-3-small" },
      warnings: [],
    }),
    getProviderStatus: vi.fn().mockResolvedValue({
      tier: "cloud_assist",
      model_plan: { llm: "gpt-4o-mini", vlm: "gpt-4o", stt: "whisper-1", tts: "tts-1", embedding: "text-embedding-3-small" },
      configured_providers: [],
      ollama_reachable: false,
    }),
    getCostEstimate: vi.fn().mockResolvedValue({
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      estimated_cost_usd: 0,
      soft_cap_tokens: 50000,
      soft_cap_usd: 2.0,
      cap_warning: false,
    }),
    setTier: vi.fn(),
    setCostCap: vi.fn(),
    testConnection: vi.fn(),
    runSmokeTest: vi.fn(),
    ...overrides,
  } as unknown as PoiseAPI;
}

describe("useHardwareSettings", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads profile, tier, provider status, and cost estimate on mount", async () => {
    const api = fakeApi();
    vi.spyOn(ipc, "listConfiguredProviders").mockResolvedValue([]);

    const { result } = renderHook(() => useHardwareSettings(api));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.profile?.cpu_cores).toBe(8);
    expect(result.current.tier?.recommended_tier).toBe("cloud_assist");
    expect(result.current.providerStatus?.tier).toBe("cloud_assist");
    expect(result.current.costEstimate?.soft_cap_tokens).toBe(50000);
  });

  it("returns null state and does not fetch when api is null", async () => {
    const { result } = renderHook(() => useHardwareSettings(null));

    expect(result.current.profile).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("surfaces an error message when a fetch fails", async () => {
    const api = fakeApi({
      getHardwareProfile: vi.fn().mockRejectedValue(new Error("sidecar unreachable")),
    });
    vi.spyOn(ipc, "listConfiguredProviders").mockResolvedValue([]);

    const { result } = renderHook(() => useHardwareSettings(api));

    await waitFor(() => expect(result.current.error).toBe("sidecar unreachable"));
  });

  it("overrideTier calls setTier and refreshes state", async () => {
    const api = fakeApi();
    vi.spyOn(ipc, "listConfiguredProviders").mockResolvedValue([]);

    const liteTier = {
      recommended_tier: "local_lite" as const,
      reason: "overridden",
      available_tiers: ["cloud_assist" as const, "local_lite" as const],
      model_plan: {
        llm: "qwen2.5:7b",
        vlm: null,
        stt: "small",
        tts: "piper",
        embedding: "nomic-embed-text",
      },
      warnings: [],
    };
    (api.setTier as ReturnType<typeof vi.fn>).mockResolvedValue(liteTier);
    // First call happens on mount (cloud_assist default from fakeApi); the
    // hook calls refresh() again after overrideTier, which should reflect
    // the now-persisted override.
    (api.getTier as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        recommended_tier: "cloud_assist",
        reason: "initial",
        available_tiers: ["cloud_assist"],
        model_plan: liteTier.model_plan,
        warnings: [],
      })
      .mockResolvedValue(liteTier);

    const { result } = renderHook(() => useHardwareSettings(api));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await result.current.overrideTier("local_lite");

    expect(api.setTier).toHaveBeenCalledWith("local_lite");
    await waitFor(() => expect(result.current.tier?.recommended_tier).toBe("local_lite"));
  });
});
