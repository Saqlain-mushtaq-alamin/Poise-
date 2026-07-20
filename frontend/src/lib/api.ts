import type {
  CostEstimate,
  HardwareProfile,
  HealthResponse,
  ProviderStatus,
  SettingValue,
  SmokeTestResult,
  TestConnectionResult,
  TierRecommendation,
} from "./types";

const DEFAULT_TIMEOUT_MS = 5000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Typed fetch wrapper around the Poise FastAPI sidecar. One instance is
 * created per app session, pointed at whatever port the sidecar reported
 * (see hooks/useSidecar.ts). */
export class PoiseAPI {
  private readonly baseUrl: string;

  constructor(port: number) {
    this.baseUrl = `http://127.0.0.1:${port}`;
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/health");
  }

  async getSetting(key: string): Promise<SettingValue> {
    return this.request<SettingValue>("GET", `/settings/${encodeURIComponent(key)}`);
  }

  async putSetting(key: string, value: string | null): Promise<SettingValue> {
    return this.request<SettingValue>("PUT", `/settings/${encodeURIComponent(key)}`, { value });
  }

  // ---- Phase 2: hardware detection + model provider layer ----

  async getHardwareProfile(): Promise<HardwareProfile> {
    return this.request<HardwareProfile>("GET", "/hardware/profile");
  }

  async getTier(): Promise<TierRecommendation> {
    return this.request<TierRecommendation>("GET", "/hardware/tier");
  }

  async setTier(tier: string): Promise<TierRecommendation> {
    return this.request<TierRecommendation>("PUT", "/hardware/tier", { tier });
  }

  async getProviderStatus(): Promise<ProviderStatus> {
    return this.request<ProviderStatus>("GET", "/provider/status");
  }

  async getCostEstimate(): Promise<CostEstimate> {
    return this.request<CostEstimate>("GET", "/provider/cost");
  }

  async setCostCap(softCapTokens: number, softCapUsd: number): Promise<CostEstimate> {
    return this.request<CostEstimate>("PUT", "/provider/cost/cap", {
      soft_cap_tokens: softCapTokens,
      soft_cap_usd: softCapUsd,
    });
  }

  async testConnection(
    provider: string,
    key?: string,
    baseUrl?: string
  ): Promise<TestConnectionResult> {
    return this.request<TestConnectionResult>("POST", "/setup/test-connection", {
      provider,
      key,
      base_url: baseUrl,
    });
  }

  async runSmokeTest(): Promise<SmokeTestResult> {
    return this.request<SmokeTestResult>("POST", "/setup/run-smoke-test");
  }

  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    timeoutMs: number = DEFAULT_TIMEOUT_MS
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new ApiError(`${method} ${path} failed with ${res.status}`, res.status);
      }

      return (await res.json()) as T;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new ApiError(`${method} ${path} timed out after ${timeoutMs}ms`);
      }
      throw new ApiError(`${method} ${path} failed: ${(err as Error).message}`);
    } finally {
      clearTimeout(timeout);
    }
  }
}
