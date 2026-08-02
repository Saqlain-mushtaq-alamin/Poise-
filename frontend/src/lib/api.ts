// Phase 1 — PoiseAPI HTTP client for communicating with the FastAPI sidecar.

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  uptime_seconds: number;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class PoiseAPI {
  public port: number;
  public baseUrl: string;

  constructor(port = 8000) {
    this.port = port;
    this.baseUrl = `http://127.0.0.1:${port}`;
  }

  setPort(port: number) {
    if (port && port > 0) {
      this.port = port;
      this.baseUrl = `http://127.0.0.1:${port}`;
      if (typeof window !== "undefined") {
        (window as unknown as { __POISE_SIDECAR_PORT__?: number }).__POISE_SIDECAR_PORT__ = port;
      }
    }
  }

  get baseUrlValue(): string {
    const globalPort = typeof window !== "undefined"
      ? (window as unknown as { __POISE_SIDECAR_PORT__?: number }).__POISE_SIDECAR_PORT__
      : undefined;
    if (globalPort && globalPort !== this.port) {
      this.setPort(globalPort);
    }
    return this.baseUrl;
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/health");
  }

  async getSetting(key: string): Promise<{ value: string }> {
    return this.request<{ value: string }>("GET", `/settings/${key}`);
  }

  async putSetting(key: string, value: string): Promise<{ value: string }> {
    return this.request<{ value: string }>("PUT", `/settings/${key}`, { value });
  }

  // ---- Hardware & Provider methods ----
  async getHardwareProfile<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/hardware/profile");
  }

  async getTier<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/hardware/tier");
  }

  async setTier<T = unknown>(tier: string): Promise<T> {
    return this.request<T>("PUT", "/hardware/tier", { tier });
  }

  async getProviderStatus<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/provider/status");
  }

  async getModelConfig<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/provider/model");
  }

  async setModelConfig<T = unknown>(model: string | null): Promise<T> {
    return this.request<T>("PUT", "/provider/model", { model });
  }

  async getCostEstimate<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/provider/cost");
  }

  async testConnection<T = unknown>(provider: string, key?: string, baseUrl?: string): Promise<T> {
    return this.request<T>("POST", "/setup/test-connection", { provider, key, base_url: baseUrl });
  }

  async runSmokeTest<T = unknown>(): Promise<T> {
    return this.request<T>("POST", "/setup/run-smoke-test");
  }

  async setCostCap<T = unknown>(softCapTokens: number, softCapUsd?: number): Promise<T> {
    return this.request<T>("PUT", "/provider/cost/cap", { soft_cap_tokens: softCapTokens, soft_cap_usd: softCapUsd ?? 0 });
  }

  // ---- Interview Session methods ----
  async createInterviewSession<T = unknown>(
    resumeId: string,
    jdId: string,
    config?: unknown,
    personaId?: string
  ): Promise<T> {
    return this.request<T>("POST", "/interview/sessions", {
      resume_id: resumeId,
      jd_id: jdId,
      config: config ?? {},
      persona_id: personaId ?? "professional",
    });
  }

  async startInterviewSession<T = unknown>(id: string): Promise<T> {
    return this.request<T>("POST", `/interview/sessions/${id}/start`);
  }

  async respondToWarmUp<T = unknown>(id: string, answer: unknown): Promise<T> {
    return this.request<T>("POST", `/interview/sessions/${id}/warmup-respond`, { text: answer });
  }

  async submitAnswer<T = unknown>(id: string, data: unknown): Promise<T> {
    return this.request<T>("POST", `/interview/sessions/${id}/answer`, data);
  }

  async endInterviewSession<T = unknown>(id: string): Promise<T> {
    return this.request<T>("POST", `/interview/sessions/${id}/end`);
  }

  async getInterviewEvaluations<T = unknown>(id: string): Promise<T> {
    return this.request<T>("GET", `/interview/sessions/${id}/evaluations`);
  }

  // ---- Voice Pipeline methods ----
  async listVoices<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/voice/tts/voices");
  }

  async synthesizeSpeechStream<T = unknown>(text: string, voice?: string): Promise<T> {
    return this.request<T>("POST", "/voice/tts/synthesize", { text, voice });
  }

  // ---- Webcam / Confidence methods ----
  async submitConfidenceFrames<T = unknown>(sessionId: string | null, frames: unknown): Promise<T> {
    return this.request<T>("POST", `/webcam/sessions/${sessionId ?? "default"}/frames`, { frames });
  }

  // ---- Setup / Personas / Resume methods ----
  async listPersonas<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/interview/personas");
  }

  async listCompanyFormats<T = unknown>(): Promise<T> {
    return this.request<T>("GET", "/interview/company-formats");
  }

  async parseResume<T = unknown>(file: File | string): Promise<T> {
    if (typeof file === "string") {
      return this.request<T>("POST", "/interview/parse-resume-text", { text: file });
    }
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${this.baseUrlValue}/interview/parse-resume`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new ApiError(`parseResume failed with ${res.status}`, res.status);
    return (await res.json()) as T;
  }

  async parseJD<T = unknown>(text: string): Promise<T> {
    return this.request<T>("POST", "/interview/parse-jd", { text });
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const baseUrl = this.baseUrlValue;
    const url = path.startsWith("http")
      ? path
      : `${baseUrl}${path.startsWith("/") ? "" : "/"}${path}`;

    const options: RequestInit = {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    };

    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        throw new ApiError(`${method} ${path} failed with ${res.status}`, res.status);
      }
      return (await res.json()) as T;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        `Network or request error: ${err instanceof Error ? err.message : String(err)}`,
        0
      );
    }
  }
}

export const api = new PoiseAPI(8000);

export async function invokeSidecar<T>(method: string, path: string, body?: unknown): Promise<T> {
  return api.request<T>(method, path, body);
}
