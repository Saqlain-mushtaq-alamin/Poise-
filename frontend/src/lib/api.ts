import type {
  AudioDeviceInfo,
  AnswerResult,
  BaselineComparisonData,
  CompanyFormat,
  ConfidenceFramePayload,
  ConfidenceSummaryData,
  ConfidenceTimelineData,
  CostEstimate,
  EvaluationRecord,
  HardwareProfile,
  HealthResponse,
  InterviewConfig,
  InterviewPlan,
  InterviewSessionResponse,
  Persona,
  ProgressPointData,
  ProviderStatus,
  SettingValue,
  SmokeTestResult,
  TestConnectionResult,
  TierRecommendation,
  VoiceInfo,
  WarmUpRespondResult,
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

  // ---- Phase 3: voice pipeline ----

  async listVoices(): Promise<VoiceInfo[]> {
    return this.request<VoiceInfo[]>("GET", "/voice/tts/voices");
  }

  async listAudioDevices(): Promise<AudioDeviceInfo[]> {
    return this.request<AudioDeviceInfo[]>("GET", "/voice/devices");
  }

  /** Returns the raw WAV byte stream from the sidecar so TTSPlayback can
   * decode and schedule chunks as they arrive, instead of waiting for the
   * whole response body. */
  async synthesizeSpeechStream(text: string, voice = "default"): Promise<ReadableStream<Uint8Array>> {
    const res = await fetch(`${this.baseUrl}/voice/tts/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice, stream: true }),
    });
    if (!res.ok || !res.body) {
      throw new ApiError(`POST /voice/tts/synthesize failed with ${res.status}`, res.status);
    }
    return res.body;
  }

  // ---- Phase 4: interview engine ----

  async listPersonas(): Promise<Persona[]> {
    return this.request<Persona[]>("GET", "/interview/personas");
  }

  async listCompanyFormats(): Promise<CompanyFormat[]> {
    return this.request<CompanyFormat[]>("GET", "/interview/company-formats");
  }

  async parseResume(file: File): Promise<{ resume_id: string }> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${this.baseUrl}/interview/parse-resume`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new ApiError(`POST /interview/parse-resume failed with ${res.status}`, res.status);
    }
    return res.json();
  }

  async parseJD(text: string): Promise<{ jd_id: string }> {
    return this.request<{ jd_id: string }>("POST", "/interview/parse-jd", { text });
  }

  async generateInterviewPlan(
    resumeId: string,
    jdId: string,
    config: Partial<InterviewConfig>
  ): Promise<InterviewPlan> {
    return this.request<InterviewPlan>("POST", "/interview/generate-plan", {
      resume_id: resumeId,
      jd_id: jdId,
      config,
    });
  }

  async createInterviewSession(
    resumeId: string,
    jdId: string,
    config: Partial<InterviewConfig>,
    personaId: string,
    sessionMode: "practice" | "exam" = "practice"
  ): Promise<InterviewSessionResponse> {
    return this.request<InterviewSessionResponse>("POST", "/interview/sessions", {
      resume_id: resumeId,
      jd_id: jdId,
      config,
      persona_id: personaId,
      session_mode: sessionMode,
    });
  }

  async startInterviewSession(sessionId: string): Promise<WarmUpRespondResult> {
    return this.request<WarmUpRespondResult>(
      "POST",
      `/interview/sessions/${sessionId}/start`
    );
  }

  async respondToWarmUp(sessionId: string, text: string): Promise<WarmUpRespondResult> {
    return this.request<WarmUpRespondResult>(
      "POST",
      `/interview/sessions/${sessionId}/warmup-respond`,
      { text }
    );
  }

  async submitAnswer(sessionId: string, text: string): Promise<AnswerResult> {
    return this.request<AnswerResult>("POST", `/interview/sessions/${sessionId}/answer`, {
      text,
    });
  }

  async endInterviewSession(sessionId: string): Promise<InterviewSessionResponse> {
    return this.request<InterviewSessionResponse>(
      "POST",
      `/interview/sessions/${sessionId}/end`
    );
  }

  async getInterviewEvaluations(sessionId: string): Promise<EvaluationRecord[]> {
    return this.request<EvaluationRecord[]>(
      "GET",
      `/interview/sessions/${sessionId}/evaluations`
    );
  }

  // ---- Phase 5: webcam confidence analysis ----

  async submitConfidenceFrames(sessionId: string, frames: ConfidenceFramePayload[]): Promise<void> {
    await this.request("POST", `/webcam/session/${sessionId}/frames`, frames);
  }

  async getConfidenceTimeline(sessionId: string): Promise<ConfidenceTimelineData> {
    return this.request<ConfidenceTimelineData>(
      "GET",
      `/webcam/session/${sessionId}/timeline`
    );
  }

  async getConfidenceSummary(sessionId: string): Promise<ConfidenceSummaryData> {
    return this.request<ConfidenceSummaryData>("GET", `/webcam/session/${sessionId}/summary`);
  }

  async getBaselineComparison(
    sessionId: string,
    warmupEndMs: number
  ): Promise<BaselineComparisonData> {
    return this.request<BaselineComparisonData>(
      "GET",
      `/webcam/session/${sessionId}/baseline-comparison?warmup_end_ms=${warmupEndMs}`
    );
  }

  async getConfidenceProgress(sessionIds: string[]): Promise<ProgressPointData[]> {
    const query = sessionIds.map((id) => `session_ids=${encodeURIComponent(id)}`).join("&");
    return this.request<ProgressPointData[]>("GET", `/webcam/progress?${query}`);
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
