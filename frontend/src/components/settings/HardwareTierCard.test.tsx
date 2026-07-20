import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HardwareProfile, TierRecommendation } from "../../lib/types";
import { HardwareTierCard } from "./HardwareTierCard";

const profile: HardwareProfile = {
  os: "windows",
  cpu_cores: 12,
  cpu_name: "Test CPU",
  ram_total_gb: 32,
  ram_available_gb: 20,
  gpus: [
    { name: "RTX 4060", vram_total_mb: 8188, vram_available_mb: 7200, driver: "nvidia", compute_capability: "8.9" },
  ],
  docker_available: true,
  ollama_available: true,
  ollama_models: [],
};

const tier: TierRecommendation = {
  recommended_tier: "local_lite",
  reason: "Detected 7.0GB free VRAM (4-7GB range).",
  available_tiers: ["cloud_assist", "local_lite"],
  model_plan: { llm: "qwen2.5:7b", vlm: null, stt: "small", tts: "piper", embedding: "nomic-embed-text" },
  warnings: ["Low RAM may cause slowdowns when other apps are also running."],
};

describe("HardwareTierCard", () => {
  it("renders detected specs and the recommendation reason", () => {
    render(
      <HardwareTierCard profile={profile} tier={tier} loading={false} onOverride={vi.fn()} onRedetect={vi.fn()} />
    );

    expect(screen.getByText(/12 cores/)).toBeInTheDocument();
    expect(screen.getByText(/RTX 4060/)).toBeInTheDocument();
    expect(screen.getByText(tier.reason)).toBeInTheDocument();
    expect(screen.getByText(/Low RAM may cause slowdowns/)).toBeInTheDocument();
  });

  it("calls onOverride when a different tier is selected", () => {
    const onOverride = vi.fn();
    render(
      <HardwareTierCard profile={profile} tier={tier} loading={false} onOverride={onOverride} onRedetect={vi.fn()} />
    );

    const select = screen.getByLabelText(/active tier/i);
    fireEvent.change(select, { target: { value: "cloud_assist" } });

    expect(onOverride).toHaveBeenCalledWith("cloud_assist");
  });

  it("calls onRedetect when the button is clicked", () => {
    const onRedetect = vi.fn();
    render(
      <HardwareTierCard profile={profile} tier={tier} loading={false} onOverride={vi.fn()} onRedetect={onRedetect} />
    );

    fireEvent.click(screen.getByRole("button", { name: /re-run detection/i }));
    expect(onRedetect).toHaveBeenCalled();
  });

  it("disables the button and shows a busy label while loading", () => {
    render(
      <HardwareTierCard profile={profile} tier={tier} loading={true} onOverride={vi.fn()} onRedetect={vi.fn()} />
    );

    const button = screen.getByRole("button", { name: /detecting/i });
    expect(button).toBeDisabled();
  });
});
