/**
 * Eye contact analysis, per Phase 5 spec §5.3. Uses each eye's iris
 * center position relative to its own corner/lid bounds to estimate gaze
 * direction — a normalized ratio near the middle in both axes reads as
 * "looking at the camera"; skewed toward an edge reads as looking away.
 *
 * This needs Face Mesh's iris refinement (landmarks 468-477) — a real,
 * documented MediaPipe capability, not a workaround. Pure geometry, fully
 * testable with synthetic iris/eye-corner coordinates.
 */
import {
  FACE,
  LEFT_EYE_BOUNDS,
  type Point3D,
  RIGHT_EYE_BOUNDS,
} from "./landmarks";

export type GazeDirection = "direct" | "away_left" | "away_right" | "down" | "up";

export interface EyeContactSignal {
  direction: GazeDirection;
  confidence: number;
  contact_ratio_30s: number;
}

// How far the iris ratio can drift from center (0.5) before we call it
// "away" rather than "direct" — tuned against the synthetic fixtures in
// eyeContact.test.ts, not calibrated against real recorded gaze data.
const DIRECT_TOLERANCE = 0.15;
const ROLLING_WINDOW_MS = 30_000;

function eyeGazeRatio(
  landmarks: Point3D[],
  irisIndex: number,
  bounds: { outer: number; inner: number; top: number; bottom: number }
): { horizontal: number; vertical: number } {
  const iris = landmarks[irisIndex];
  const outer = landmarks[bounds.outer];
  const inner = landmarks[bounds.inner];
  const top = landmarks[bounds.top];
  const bottom = landmarks[bounds.bottom];

  const width = inner.x - outer.x;
  const height = bottom.y - top.y;

  const horizontal = width !== 0 ? (iris.x - outer.x) / width : 0.5;
  const vertical = height !== 0 ? (iris.y - top.y) / height : 0.5;

  return { horizontal, vertical };
}

function classifyDirection(
  horizontal: number,
  vertical: number,
  baselineH: number = 0.5,
  baselineV: number = 0.5
): { direction: GazeDirection; confidence: number } {
  const horizontalOffset = Math.abs(horizontal - baselineH);
  const verticalOffset = Math.abs(vertical - baselineV);

  if (horizontalOffset <= DIRECT_TOLERANCE && verticalOffset <= DIRECT_TOLERANCE) {
    const confidence = 1 - Math.max(horizontalOffset, verticalOffset) / DIRECT_TOLERANCE;
    return { direction: "direct", confidence: clamp01(confidence) };
  }

  // Whichever axis is further off-center dominates the classification.
  if (horizontalOffset >= verticalOffset) {
    const direction = horizontal < baselineH ? "away_left" : "away_right";
    return { direction, confidence: clamp01(horizontalOffset / 0.5) };
  }

  const direction = vertical < baselineV ? "up" : "down";
  return { direction, confidence: clamp01(verticalOffset / 0.5) };
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

export class EyeContactAnalyzer {
  private history: { timestampMs: number; isDirect: boolean }[] = [];
  private baselineHorizontal: number = 0.5;
  private baselineVertical: number = 0.5;
  private isCalibrated: boolean = false;
  private calibrationSamples: { h: number; v: number }[] = [];

  setBaseline(horizontal: number, vertical: number): void {
    this.baselineHorizontal = horizontal;
    this.baselineVertical = vertical;
    this.isCalibrated = true;
  }

  getBaseline(): { horizontal: number; vertical: number; isCalibrated: boolean } {
    return {
      horizontal: this.baselineHorizontal,
      vertical: this.baselineVertical,
      isCalibrated: this.isCalibrated,
    };
  }

  processFrame(landmarks: Point3D[], timestampMs: number): EyeContactSignal {
    const right = eyeGazeRatio(landmarks, FACE.RIGHT_IRIS_CENTER, RIGHT_EYE_BOUNDS);
    const left = eyeGazeRatio(landmarks, FACE.LEFT_IRIS_CENTER, LEFT_EYE_BOUNDS);

    const horizontal = (right.horizontal + left.horizontal) / 2;
    const vertical = (right.vertical + left.vertical) / 2;

    // Auto-calibrate on the initial 15 frames if candidate is roughly centered
    if (!this.isCalibrated && this.calibrationSamples.length < 15) {
      this.calibrationSamples.push({ h: horizontal, v: vertical });
      if (this.calibrationSamples.length === 15) {
        const avgH = this.calibrationSamples.reduce((s, c) => s + c.h, 0) / 15;
        const avgV = this.calibrationSamples.reduce((s, c) => s + c.v, 0) / 15;
        if (Math.abs(avgH - 0.5) < 0.25 && Math.abs(avgV - 0.5) < 0.25) {
          this.baselineHorizontal = avgH;
          this.baselineVertical = avgV;
          this.isCalibrated = true;
        }
      }
    }

    const { direction, confidence } = classifyDirection(
      horizontal,
      vertical,
      this.baselineHorizontal,
      this.baselineVertical
    );

    this.history.push({ timestampMs, isDirect: direction === "direct" });
    this.history = this.history.filter((h) => timestampMs - h.timestampMs <= ROLLING_WINDOW_MS);

    const contactRatio =
      this.history.length > 0
        ? this.history.filter((h) => h.isDirect).length / this.history.length
        : 0;

    return {
      direction,
      confidence: round(confidence),
      contact_ratio_30s: round(contactRatio),
    };
  }

  reset(): void {
    this.history = [];
    this.calibrationSamples = [];
    this.isCalibrated = false;
    this.baselineHorizontal = 0.5;
    this.baselineVertical = 0.5;
  }
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}
