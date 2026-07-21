/**
 * Head pose + stability, per Phase 5 spec §5.4.
 *
 * `computeHeadPose` is a lightweight geometric heuristic — not a full 6DOF
 * solvePnP fit — using three landmarks (both eye outer corners + nose
 * tip) to estimate roll (eye-line tilt), yaw (nose horizontal offset from
 * the eye midpoint, normalized by eye separation), and pitch (nose
 * vertical offset from the eye line, normalized by face height). That's
 * enough to answer "is the head turning/tilting/nodding", which is what
 * stability tracking needs; it is not enough to answer "what's the exact
 * angle in degrees" the way a calibrated solvePnP solution would be.
 * Tested against synthetic landmark sets with known relative offsets
 * (e.g. "nose shifted right of the eye midpoint"), not against real
 * recorded head-pose ground truth.
 *
 * Stability itself — variance of pose over a 10s window — is exact,
 * ordinary statistics regardless of how the underlying angles were
 * derived.
 */
import { distance, FACE, type Point3D } from "./landmarks";

export interface HeadPose {
  pitch: number;
  yaw: number;
  roll: number;
}

export type MovementPattern = "stable" | "nodding" | "shaking" | "fidgeting";

export interface HeadStabilitySignal extends HeadPose {
  stability_score: number;
  movement_pattern: MovementPattern;
}

const STABILITY_WINDOW_MS = 10_000;
// Variance (in normalized heuristic-degree units squared) above which we
// no longer consider the head "stable" — tuned against this module's own
// synthetic fixtures, see the module docstring.
const STABLE_VARIANCE_THRESHOLD = 4;
const DOMINANT_AXIS_RATIO = 1.5; // how much bigger one axis's variance must be to "dominate"

export function computeHeadPose(landmarks: Point3D[]): HeadPose {
  const leftEye = landmarks[FACE.LEFT_EYE_OUTER];
  const rightEye = landmarks[FACE.RIGHT_EYE_OUTER];
  const nose = landmarks[FACE.NOSE_TIP];
  const forehead = landmarks[FACE.FOREHEAD];
  const chin = landmarks[FACE.CHIN];

  const eyeMidpoint = { x: (leftEye.x + rightEye.x) / 2, y: (leftEye.y + rightEye.y) / 2 };
  const eyeDistance = distance(leftEye, rightEye) || 1;
  const faceHeight = distance(forehead, chin) || 1;

  const roll = (Math.atan2(rightEye.y - leftEye.y, rightEye.x - leftEye.x) * 180) / Math.PI;
  const yaw = ((nose.x - eyeMidpoint.x) / eyeDistance) * 90;
  const pitch = ((nose.y - eyeMidpoint.y) / faceHeight) * 90;

  return { pitch: round(pitch), yaw: round(yaw), roll: round(roll) };
}

function variance(values: number[]): number {
  if (values.length === 0) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length;
}

export class HeadStabilityTracker {
  private history: { timestampMs: number; pose: HeadPose }[] = [];

  processFrame(landmarks: Point3D[], timestampMs: number): HeadStabilitySignal {
    const pose = computeHeadPose(landmarks);
    this.history.push({ timestampMs, pose });
    this.history = this.history.filter(
      (h) => timestampMs - h.timestampMs <= STABILITY_WINDOW_MS
    );

    const pitchVar = variance(this.history.map((h) => h.pose.pitch));
    const yawVar = variance(this.history.map((h) => h.pose.yaw));
    const rollVar = variance(this.history.map((h) => h.pose.roll));
    const totalVariance = pitchVar + yawVar + rollVar;

    const stabilityScore = clamp01(1 - totalVariance / (STABLE_VARIANCE_THRESHOLD * 4));
    const movementPattern = classifyMovementPattern(pitchVar, yawVar, rollVar, totalVariance);

    return {
      ...pose,
      stability_score: round(stabilityScore),
      movement_pattern: movementPattern,
    };
  }

  reset(): void {
    this.history = [];
  }
}

function classifyMovementPattern(
  pitchVar: number,
  yawVar: number,
  rollVar: number,
  totalVariance: number
): MovementPattern {
  if (totalVariance < STABLE_VARIANCE_THRESHOLD) return "stable";

  const maxVar = Math.max(pitchVar, yawVar, rollVar);
  if (maxVar === pitchVar && pitchVar > DOMINANT_AXIS_RATIO * (yawVar + rollVar || 1)) {
    return "nodding";
  }
  if (maxVar === yawVar && yawVar > DOMINANT_AXIS_RATIO * (pitchVar + rollVar || 1)) {
    return "shaking";
  }
  return "fidgeting";
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}
