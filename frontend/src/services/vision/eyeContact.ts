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

function classifyDirection(horizontal: number, vertical: number): { direction: GazeDirection; confidence: number } {
  const horizontalOffset = Math.abs(horizontal - 0.5);
  const verticalOffset = Math.abs(vertical - 0.5);

  if (horizontalOffset <= DIRECT_TOLERANCE && verticalOffset <= DIRECT_TOLERANCE) {
    const confidence = 1 - Math.max(horizontalOffset, verticalOffset) / DIRECT_TOLERANCE;
    return { direction: "direct", confidence: clamp01(confidence) };
  }

  // Whichever axis is further off-center dominates the classification.
  if (horizontalOffset >= verticalOffset) {
    const direction = horizontal < 0.5 ? "away_left" : "away_right";
    return { direction, confidence: clamp01(horizontalOffset / 0.5) };
  }

  const direction = vertical < 0.5 ? "up" : "down";
  return { direction, confidence: clamp01(verticalOffset / 0.5) };
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

export class EyeContactAnalyzer {
  private history: { timestampMs: number; isDirect: boolean }[] = [];

  processFrame(landmarks: Point3D[], timestampMs: number): EyeContactSignal {
    const right = eyeGazeRatio(landmarks, FACE.RIGHT_IRIS_CENTER, RIGHT_EYE_BOUNDS);
    const left = eyeGazeRatio(landmarks, FACE.LEFT_IRIS_CENTER, LEFT_EYE_BOUNDS);

    const horizontal = (right.horizontal + left.horizontal) / 2;
    const vertical = (right.vertical + left.vertical) / 2;
    const { direction, confidence } = classifyDirection(horizontal, vertical);

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
  }
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}
