/**
 * Blink detection via Eye Aspect Ratio (EAR) — Soukupová & Čech's 2016
 * formula, the standard lightweight approach (used ahead of training any
 * classifier): EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||) for the six
 * eye landmarks [corner, top1, top2, corner, bottom1, bottom2]. EAR drops
 * sharply when the eye closes and stays high (~0.25-0.35) when open.
 *
 * Real, well-established math — fully testable with synthetic eye-shaped
 * point sets without a camera or MediaPipe.
 */
import { distance, LEFT_EYE_EAR_POINTS, type Point3D, RIGHT_EYE_EAR_POINTS } from "./landmarks";

export interface BlinkSignal {
  ear_left: number;
  ear_right: number;
  is_blinking: boolean;
  blinks_per_minute: number;
  assessment: "normal" | "elevated" | "low";
}

export const EAR_BLINK_THRESHOLD = 0.2;
const MIN_BLINK_DURATION_MS = 100;
const MAX_BLINK_DURATION_MS = 400;
const RATE_WINDOW_MS = 60_000;

export function computeEAR(landmarks: Point3D[], points: readonly number[]): number {
  const [p1, p2, p3, p4, p5, p6] = points.map((i) => landmarks[i]);
  const vertical = distance(p2, p6) + distance(p3, p5);
  const horizontal = distance(p1, p4);
  if (horizontal === 0) return 0;
  return vertical / (2 * horizontal);
}

interface CandidateBlink {
  startMs: number;
}

/**
 * Stateful across frames — tracks eye-closure duration (to distinguish a
 * genuine blink from a longer, deliberate eye closure) and a rolling
 * 60-second window of confirmed blinks for the per-minute rate.
 */
export class BlinkDetector {
  private candidate: CandidateBlink | null = null;
  private confirmedBlinkTimestamps: number[] = [];
  private wasBelowThreshold = false;

  processFrame(landmarks: Point3D[], timestampMs: number): BlinkSignal {
    const earLeft = computeEAR(landmarks, LEFT_EYE_EAR_POINTS);
    const earRight = computeEAR(landmarks, RIGHT_EYE_EAR_POINTS);
    const avgEar = (earLeft + earRight) / 2;
    const isBelowThreshold = avgEar < EAR_BLINK_THRESHOLD;

    if (isBelowThreshold && !this.wasBelowThreshold) {
      // Eye just closed — start tracking a candidate blink.
      this.candidate = { startMs: timestampMs };
    } else if (!isBelowThreshold && this.wasBelowThreshold && this.candidate) {
      // Eye just reopened — confirm as a blink only if the closure
      // duration falls in the genuine-blink range (100-400ms). Longer
      // closures are a deliberate eye-close, not a blink.
      const duration = timestampMs - this.candidate.startMs;
      if (duration >= MIN_BLINK_DURATION_MS && duration <= MAX_BLINK_DURATION_MS) {
        this.confirmedBlinkTimestamps.push(timestampMs);
      }
      this.candidate = null;
    }
    this.wasBelowThreshold = isBelowThreshold;

    this.confirmedBlinkTimestamps = this.confirmedBlinkTimestamps.filter(
      (t) => timestampMs - t <= RATE_WINDOW_MS
    );
    // Extrapolate to a per-minute rate even before a full 60s of history
    // has accumulated, so the very first minute of a session isn't stuck
    // reporting a misleadingly low rate.
    const elapsedForRate = Math.min(timestampMs, RATE_WINDOW_MS) || RATE_WINDOW_MS;
    const blinksPerMinute = (this.confirmedBlinkTimestamps.length / elapsedForRate) * 60_000;

    return {
      ear_left: round(earLeft),
      ear_right: round(earRight),
      is_blinking: isBelowThreshold,
      blinks_per_minute: round(blinksPerMinute),
      assessment: assessBlinkRate(blinksPerMinute),
    };
  }

  reset(): void {
    this.candidate = null;
    this.confirmedBlinkTimestamps = [];
    this.wasBelowThreshold = false;
  }
}

export function assessBlinkRate(blinksPerMinute: number): BlinkSignal["assessment"] {
  if (blinksPerMinute > 25) return "elevated";
  if (blinksPerMinute < 10) return "low";
  return "normal";
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}
