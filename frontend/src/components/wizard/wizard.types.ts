// Shared types for the First-Run Wizard (Phase 9.1)
// Drop into: frontend/src/components/wizard/wizard.types.ts

export type WizardStepId =
  | "welcome"
  | "hardware-scan"
  | "tier-confirm"
  | "model-download"
  | "api-key-setup"
  | "audio-check"
  | "camera-check"
  | "quick-demo"
  | "complete";

export interface WizardStepMeta {
  id: WizardStepId;
  label: string;
  /** Steps that only apply to certain provider tiers are filtered at runtime. */
  showFor?: Array<"local-lite" | "local-full" | "cloud">;
  optional?: boolean;
}

// Order matches Phase 9.1 spec. Filtering (e.g. skipping "model-download"
// on Cloud tier, or "api-key-setup" on Local tiers) happens in FirstRunWizard.
export const WIZARD_STEPS: WizardStepMeta[] = [
  { id: "welcome", label: "Welcome" },
  { id: "hardware-scan", label: "Hardware Scan" },
  { id: "tier-confirm", label: "Confirm Tier" },
  { id: "model-download", label: "Download Models", showFor: ["local-lite", "local-full"] },
  { id: "api-key-setup", label: "API Key", showFor: ["cloud"] },
  { id: "audio-check", label: "Audio Check" },
  { id: "camera-check", label: "Camera Check", optional: true },
  { id: "quick-demo", label: "Quick Demo" },
  { id: "complete", label: "Complete" },
];

export type HardwareTier = "cloud" | "local-lite" | "local-full";

export interface HardwareScanResult {
  cpu: string;
  ramGb: number;
  gpu: string | null;
  vramGb: number | null;
  cudaAvailable: boolean;
  recommendedTier: HardwareTier;
}

export interface WizardState {
  currentStepIndex: number;
  hardware: HardwareScanResult | null;
  selectedTier: HardwareTier | null;
  apiProvider: string | null;
  apiKeyValid: boolean;
  modelsDownloaded: boolean;
  micTested: boolean;
  cameraTested: boolean;
  cameraSkipped: boolean;
  demoCompleted: boolean;
}

export const initialWizardState: WizardState = {
  currentStepIndex: 0,
  hardware: null,
  selectedTier: null,
  apiProvider: null,
  apiKeyValid: false,
  modelsDownloaded: false,
  micTested: false,
  cameraTested: false,
  cameraSkipped: false,
  demoCompleted: false,
};
