import { describe, expect, it } from "vitest";

import { ConfidenceCoach, type TrendSnapshot } from "./confidenceCoach";

function snapshot(overrides: Partial<TrendSnapshot> = {}): TrendSnapshot {
  return {
    timestampMs: 0,
    eyeContactRatio: 0.8,
    stabilityScore: 0.9,
    expression: "neutral",
    blinksPerMinute: 16,
    gestureAssessment: "natural",
    ...overrides,
  };
}

describe("ConfidenceCoach", () => {
  it("gives no tip when every signal is healthy", () => {
    const coach = new ConfidenceCoach();
    expect(coach.analyzeTrend(snapshot({ timestampMs: 0 }))).toBeNull();
  });

  it("does not tip on low eye contact until it's been sustained for 15s", () => {
    const coach = new ConfidenceCoach();
    coach.analyzeTrend(snapshot({ timestampMs: 0, eyeContactRatio: 0.2 }));
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 5000, eyeContactRatio: 0.2 }));
    expect(tip).toBeNull();
  });

  it("tips on eye contact once it's been low for 15s+", () => {
    const coach = new ConfidenceCoach();
    coach.analyzeTrend(snapshot({ timestampMs: 0, eyeContactRatio: 0.2 }));
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 15_000, eyeContactRatio: 0.2 }));
    expect(tip?.category).toBe("eye_contact");
    expect(tip?.severity).toBe("gentle");
  });

  it("resets the sustained-low-eye-contact timer if contact recovers", () => {
    const coach = new ConfidenceCoach();
    coach.analyzeTrend(snapshot({ timestampMs: 0, eyeContactRatio: 0.2 }));
    coach.analyzeTrend(snapshot({ timestampMs: 5000, eyeContactRatio: 0.8 })); // recovers
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 15_000, eyeContactRatio: 0.2 }));
    expect(tip).toBeNull(); // only been low again for 0s at this point
  });

  it("tips immediately on low stability (no sustain requirement)", () => {
    const coach = new ConfidenceCoach();
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 0, stabilityScore: 0.3 }));
    expect(tip?.category).toBe("stability");
  });

  it("tips on anxious expression sustained for 20s+", () => {
    const coach = new ConfidenceCoach();
    coach.analyzeTrend(snapshot({ timestampMs: 0, expression: "anxious" }));
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 20_000, expression: "anxious" }));
    expect(tip?.category).toBe("expression");
  });

  it("tips on elevated blink rate", () => {
    const coach = new ConfidenceCoach();
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 0, blinksPerMinute: 35 }));
    expect(tip?.category).toBe("breathing");
    expect(tip?.severity).toBe("important");
    expect(tip?.exercise).toBeDefined();
  });

  it("tips on defensive gesture (crossed arms)", () => {
    const coach = new ConfidenceCoach();
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 0, gestureAssessment: "defensive" }));
    expect(tip?.category).toBe("posture");
  });

  it("enforces a 30s cooldown between tips", () => {
    const coach = new ConfidenceCoach();
    const first = coach.analyzeTrend(snapshot({ timestampMs: 0, stabilityScore: 0.3 }));
    expect(first).not.toBeNull();

    const second = coach.analyzeTrend(snapshot({ timestampMs: 10_000, stabilityScore: 0.3 }));
    expect(second).toBeNull(); // still within 30s cooldown
  });

  it("allows a new tip once the cooldown has elapsed", () => {
    const coach = new ConfidenceCoach();
    coach.analyzeTrend(snapshot({ timestampMs: 0, stabilityScore: 0.3 }));
    const later = coach.analyzeTrend(snapshot({ timestampMs: 30_001, stabilityScore: 0.3 }));
    expect(later).not.toBeNull();
  });

  it("eye contact takes priority over stability when both conditions are met", () => {
    const coach = new ConfidenceCoach();
    // First call only accumulates the sustained-low-eye-contact timer —
    // stability is healthy here so it doesn't consume the cooldown itself.
    coach.analyzeTrend(snapshot({ timestampMs: 0, eyeContactRatio: 0.2, stabilityScore: 0.9 }));
    const tip = coach.analyzeTrend(
      snapshot({ timestampMs: 15_000, eyeContactRatio: 0.2, stabilityScore: 0.3 })
    );
    expect(tip?.category).toBe("eye_contact");
  });

  it("reset() clears sustained-state timers and the cooldown", () => {
    const coach = new ConfidenceCoach();
    coach.analyzeTrend(snapshot({ timestampMs: 0, stabilityScore: 0.3 }));
    coach.reset();

    // Immediately after reset, a fresh low-stability reading should tip
    // again even though we're "within" what would have been the cooldown.
    const tip = coach.analyzeTrend(snapshot({ timestampMs: 1000, stabilityScore: 0.3 }));
    expect(tip).not.toBeNull();
  });
});
