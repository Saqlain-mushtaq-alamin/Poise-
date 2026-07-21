/**
 * Real-time micro-coaching, per Phase 5 spec §5.10. Every trigger is a
 * deterministic threshold check over signals this module already
 * computes — same "no LLM needed for a yes/no rule" philosophy as
 * Phase 4's `PressureSimulator`. Only shown in Practice Mode, never Exam
 * Mode (that's a caller-side concern — this class doesn't know which
 * mode it's in, it just decides *what* tip fits, not *whether* to show
 * one at all).
 */

export type CoachingCategory = "eye_contact" | "stability" | "expression" | "posture" | "breathing";
export type CoachingSeverity = "gentle" | "important";

export interface CoachingTip {
  category: CoachingCategory;
  message: string;
  severity: CoachingSeverity;
  exercise?: string;
}

export interface TrendSnapshot {
  timestampMs: number;
  eyeContactRatio: number; // 0-1, rolling ratio (already computed by EyeContactAnalyzer)
  stabilityScore: number; // 0-1
  expression: string;
  blinksPerMinute: number;
  gestureAssessment?: "natural" | "too_still" | "excessive" | "defensive";
}

const TIP_COOLDOWN_MS = 30_000;
const LOW_EYE_CONTACT_THRESHOLD = 0.4;
const LOW_EYE_CONTACT_SUSTAINED_MS = 15_000;
const LOW_STABILITY_THRESHOLD = 0.5;
const ANXIOUS_SUSTAINED_MS = 20_000;
const HIGH_BLINK_RATE_THRESHOLD = 30;

export class ConfidenceCoach {
  private lastTipAtMs = -Infinity;
  private lowEyeContactSinceMs: number | null = null;
  private anxiousSinceMs: number | null = null;

  analyzeTrend(snapshot: TrendSnapshot): CoachingTip | null {
    this.updateSustainedState(snapshot);

    if (snapshot.timestampMs - this.lastTipAtMs < TIP_COOLDOWN_MS) {
      return null;
    }

    const tip = this.pickTip(snapshot);
    if (tip) {
      this.lastTipAtMs = snapshot.timestampMs;
    }
    return tip;
  }

  private updateSustainedState(snapshot: TrendSnapshot): void {
    if (snapshot.eyeContactRatio < LOW_EYE_CONTACT_THRESHOLD) {
      this.lowEyeContactSinceMs ??= snapshot.timestampMs;
    } else {
      this.lowEyeContactSinceMs = null;
    }

    if (snapshot.expression === "anxious") {
      this.anxiousSinceMs ??= snapshot.timestampMs;
    } else {
      this.anxiousSinceMs = null;
    }
  }

  private pickTip(snapshot: TrendSnapshot): CoachingTip | null {
    if (
      this.lowEyeContactSinceMs !== null &&
      snapshot.timestampMs - this.lowEyeContactSinceMs >= LOW_EYE_CONTACT_SUSTAINED_MS
    ) {
      return {
        category: "eye_contact",
        message: "Try looking at the camera lens — it reads as eye contact.",
        severity: "gentle",
      };
    }

    if (snapshot.stabilityScore < LOW_STABILITY_THRESHOLD) {
      return {
        category: "stability",
        message: "Take a breath and plant your feet — it helps you stay still.",
        severity: "gentle",
      };
    }

    if (
      this.anxiousSinceMs !== null &&
      snapshot.timestampMs - this.anxiousSinceMs >= ANXIOUS_SUSTAINED_MS
    ) {
      return {
        category: "expression",
        message: "Smile slightly when you start your answer — it naturally calms nerves.",
        severity: "gentle",
      };
    }

    if (snapshot.blinksPerMinute > HIGH_BLINK_RATE_THRESHOLD) {
      return {
        category: "breathing",
        message: "You're blinking quickly — pause and take a slow breath.",
        severity: "important",
        exercise: "Try the 4-7-8 breathing technique: inhale 4s, hold 7s, exhale 8s.",
      };
    }

    if (snapshot.gestureAssessment === "defensive") {
      return {
        category: "posture",
        message: "Sit up slightly and uncross your arms — open posture projects confidence.",
        severity: "important",
      };
    }

    return null;
  }

  reset(): void {
    this.lastTipAtMs = -Infinity;
    this.lowEyeContactSinceMs = null;
    this.anxiousSinceMs = null;
  }
}
