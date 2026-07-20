/** Mirrors src-tauri's SidecarStatus (see src-tauri/src/sidecar.rs) and
 * contracts/types/index.d.ts. Keep these in sync by hand until Phase 9's
 * codegen step is in place. */
export type SidecarState = "starting" | "healthy" | "unhealthy" | "stopped";

export interface SidecarStatus {
  port: number;
  status: SidecarState;
  uptime_seconds: number;
  restart_count: number;
}

export interface HealthResponse {
  status: "ok";
  version: string;
  database: "connected" | "disconnected";
  uptime_seconds: number;
}

export interface SettingValue {
  value: string | null;
}

// ---- Phase 2: hardware detection + model provider layer ----

export type GPUDriver = "nvidia" | "amd" | "apple" | "intel";

export interface GPUInfo {
  name: string;
  vram_total_mb: number;
  vram_available_mb: number;
  driver: GPUDriver;
  compute_capability: string | null;
}

export interface HardwareProfile {
  os: "windows" | "macos" | "linux";
  cpu_cores: number;
  cpu_name: string;
  ram_total_gb: number;
  ram_available_gb: number;
  gpus: GPUInfo[];
  docker_available: boolean;
  ollama_available: boolean;
  ollama_models: string[];
}

export type HardwareTier = "local_full" | "local_lite" | "cloud_assist";

export interface ModelPlan {
  llm: string;
  vlm: string | null;
  stt: string;
  tts: string;
  embedding: string;
}

export interface TierRecommendation {
  recommended_tier: HardwareTier;
  reason: string;
  available_tiers: HardwareTier[];
  model_plan: ModelPlan;
  warnings: string[];
}

export type ApiProvider = "openai" | "anthropic" | "google" | "groq" | "custom";

export interface ProviderStatus {
  tier: HardwareTier;
  model_plan: ModelPlan;
  configured_providers: string[];
  ollama_reachable: boolean;
}

export interface CostEstimate {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  soft_cap_tokens: number;
  soft_cap_usd: number;
  cap_warning: boolean;
}

export interface TestConnectionResult {
  provider: string;
  success: boolean;
  latency_ms: number | null;
  models_available: number | null;
  error?: string | null;
}

export interface SmokeTestResult {
  success: boolean;
  latency_ms: number | null;
  sample_output: string | null;
  error?: string | null;
}
