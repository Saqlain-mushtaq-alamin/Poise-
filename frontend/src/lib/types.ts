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

// ---- Phase 3: voice pipeline ----

export interface VoiceInfo {
  id: string;
  name: string;
  language: string;
  gender: string;
  sample_url: string | null;
}

export interface AudioDeviceInfo {
  id: string;
  name: string;
  is_default: boolean;
}

export interface VadStatusMessage {
  is_speech: boolean;
  probability: number;
  timestamp_ms: number;
}

export interface TranscriptionSegmentMessage {
  text: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
  is_partial: boolean;
  language: string | null;
}

// ---- Phase 5: webcam confidence analysis ----

export interface ConfidenceEyeContact {
  direction: "direct" | "away_left" | "away_right" | "down" | "up";
  confidence: number;
  contact_ratio_30s: number;
}

export interface ConfidenceHeadStability {
  pitch: number;
  yaw: number;
  roll: number;
  stability_score: number;
  movement_pattern: "stable" | "nodding" | "shaking" | "fidgeting";
}

export interface ConfidenceBlink {
  ear_left: number;
  ear_right: number;
  is_blinking: boolean;
  blinks_per_minute: number;
  assessment: "normal" | "elevated" | "low";
}

export interface ConfidenceGesture {
  hand_position: "resting" | "gesturing" | "face_touching" | "fidgeting" | "crossed_arms";
  gesture_frequency: number;
  assessment: "natural" | "too_still" | "excessive" | "defensive";
}

export interface ConfidenceFramePayload {
  timestamp_ms: number;
  eye_contact: ConfidenceEyeContact;
  head_stability: ConfidenceHeadStability;
  blink_rate: ConfidenceBlink;
  expression: string;
  gesture?: ConfidenceGesture | null;
  composite_score: number;
}

export interface NotableMoment {
  timestamp_ms: number;
  description: string;
  composite_score: number;
}

export interface ConfidenceSummaryData {
  avg_eye_contact_ratio: number;
  avg_stability_score: number;
  avg_blink_rate: number;
  dominant_expression: string;
  composite_score: number;
  notable_moments: NotableMoment[];
  frame_count: number;
}

export interface ConfidenceTimelineData {
  session_id: string;
  frames: ConfidenceFramePayload[];
  summary: ConfidenceSummaryData;
}

export interface BaselineComparisonData {
  warmup_confidence: number;
  interview_confidence: number;
  confidence_delta: number;
  worst_drop_timestamp_ms: number | null;
  recovery_pattern: "quick_recovery" | "gradual_decline" | "sustained_drop" | "no_drop";
}

export interface ProgressPointData {
  session_id: string;
  eye_contact_ratio: number;
  stability_score: number;
  expression_positivity: number;
  composite_confidence: number;
}

// ---- Phase 4: interview engine ----

export interface Persona {
  id: string;
  name: string;
  style: string;
  voice: string;
  system_prompt: string;
}

export interface CompanyFormat {
  id: string;
  name: string;
  structure: string[];
  framework: string;
  scoring_note: string;
  principles: string[];
}

export interface InterviewConfig {
  duration_minutes: number;
  include_behavioral: boolean;
  include_technical: boolean;
  include_coding: boolean;
  include_system_design: boolean;
  difficulty: "easy" | "medium" | "hard";
  persona: string;
  company_format: string | null;
}

export interface PlannedQuestion {
  id: string;
  text: string;
  follow_ups: string[];
  evaluation_criteria: string[];
  difficulty: string;
  skills_tested: string[];
  source: string;
}

export interface InterviewSection {
  type: string;
  title: string;
  questions: PlannedQuestion[];
  time_budget_minutes: number;
}

export interface InterviewPlan {
  sections: InterviewSection[];
  estimated_duration_minutes: number;
  coverage_matrix: Record<string, string[]>;
}

export interface ResumeData {
  full_text: string;
  name: string | null;
  summary: string | null;
  skills: { name: string; category: string | null }[];
  experience: {
    company: string;
    title: string;
    start_date: string | null;
    end_date: string | null;
    description: string | null;
    highlights: string[];
  }[];
  education: { institution: string; degree: string | null }[];
  projects: { name: string; description: string | null; technologies: string[] }[];
  certifications: string[];
}

export interface JobDescriptionData {
  title: string;
  company: string | null;
  required_skills: string[];
  preferred_skills: string[];
  responsibilities: string[];
  experience_level: string | null;
  domain: string | null;
}

export interface InterviewSessionResponse {
  session_id: string;
  state: string;
  persona_id: string;
  session_mode: string;
  plan: InterviewPlan | null;
}

export interface WarmUpRespondResult {
  message: string;
  is_complete: boolean;
  first_question?: string | null;
  question_id?: string | null;
}

export interface AnswerResult {
  score: number;
  feedback: string;
  reaction: string | null;
  next_action: "follow_up" | "next_question" | "session_complete";
  next_message?: string | null;
  next_question_id?: string | null;
  framework_missing: string[];
}

export interface EvaluationRecord {
  question_id: string;
  question_text: string;
  is_follow_up: boolean;
  answer_text: string | null;
  score: number | null;
  feedback: string | null;
}
