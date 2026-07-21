/**
 * Hand & gesture analysis from Pose landmarks, per Phase 5 spec §5.11.
 * Classifies wrist position relative to face/shoulders/hips into a small
 * set of readable categories, then tracks how often the classification
 * changes (a proxy for gesture frequency) over a rolling window.
 *
 * Pure geometry over Pose's 33 landmarks — no camera, no model.
 */
import { distance, POSE, type PoseLandmarks } from "./landmarks";

export type HandPosition =
  | "resting"
  | "gesturing"
  | "face_touching"
  | "fidgeting"
  | "crossed_arms";

export type GestureAssessment = "natural" | "too_still" | "excessive" | "defensive";

export interface GestureSignal {
  hand_position: HandPosition;
  gesture_frequency: number; // classified position changes per minute
  assessment: GestureAssessment;
}

const FACE_TOUCH_DISTANCE_RATIO = 0.35; // wrist-to-nose distance, as a fraction of shoulder width
const RESTING_HIP_DISTANCE_RATIO = 0.3; // wrist-to-hip distance, as a fraction of shoulder width
const ROLLING_WINDOW_MS = 60_000;
const TOO_STILL_THRESHOLD = 2; // changes/min
const EXCESSIVE_THRESHOLD = 25; // changes/min

function classifyHandPosition(pose: PoseLandmarks): HandPosition {
  const leftShoulder = pose[POSE.LEFT_SHOULDER];
  const rightShoulder = pose[POSE.RIGHT_SHOULDER];
  const leftWrist = pose[POSE.LEFT_WRIST];
  const rightWrist = pose[POSE.RIGHT_WRIST];
  const nose = pose[POSE.NOSE];
  const leftHip = pose[POSE.LEFT_HIP];
  const rightHip = pose[POSE.RIGHT_HIP];

  const shoulderWidth = distance(leftShoulder, rightShoulder) || 1;

  const leftToNose = distance(leftWrist, nose) / shoulderWidth;
  const rightToNose = distance(rightWrist, nose) / shoulderWidth;
  if (leftToNose < FACE_TOUCH_DISTANCE_RATIO || rightToNose < FACE_TOUCH_DISTANCE_RATIO) {
    return "face_touching";
  }

  // Crossed arms: each wrist is near the *opposite* shoulder, both roughly
  // at shoulder/chest height.
  const leftWristNearRightShoulder = distance(leftWrist, rightShoulder) / shoulderWidth < 0.5;
  const rightWristNearLeftShoulder = distance(rightWrist, leftShoulder) / shoulderWidth < 0.5;
  if (leftWristNearRightShoulder && rightWristNearLeftShoulder) {
    return "crossed_arms";
  }

  const leftToHip = distance(leftWrist, leftHip) / shoulderWidth;
  const rightToHip = distance(rightWrist, rightHip) / shoulderWidth;
  const bothNearHips =
    leftToHip < RESTING_HIP_DISTANCE_RATIO && rightToHip < RESTING_HIP_DISTANCE_RATIO;
  if (bothNearHips) {
    return "resting";
  }

  // One or both hands raised above shoulder height, away from the face —
  // read as active gesturing rather than fidgeting by default; the
  // frequency-based assessment (see GestureAnalyzer) is what actually
  // distinguishes natural gesturing from fidgeting over time, not a
  // single frame's classification.
  const leftRaised = leftWrist.y < leftShoulder.y;
  const rightRaised = rightWrist.y < rightShoulder.y;
  if (leftRaised || rightRaised) {
    return "gesturing";
  }

  return "fidgeting";
}

export class GestureAnalyzer {
  private history: { timestampMs: number; position: HandPosition }[] = [];
  private lastPosition: HandPosition | null = null;
  private changeTimestamps: number[] = [];

  processFrame(pose: PoseLandmarks, timestampMs: number): GestureSignal {
    const position = classifyHandPosition(pose);

    if (this.lastPosition !== null && position !== this.lastPosition) {
      this.changeTimestamps.push(timestampMs);
    }
    this.lastPosition = position;
    this.changeTimestamps = this.changeTimestamps.filter(
      (t) => timestampMs - t <= ROLLING_WINDOW_MS
    );

    this.history.push({ timestampMs, position });
    this.history = this.history.filter((h) => timestampMs - h.timestampMs <= ROLLING_WINDOW_MS);

    const elapsedForRate = Math.min(timestampMs, ROLLING_WINDOW_MS) || ROLLING_WINDOW_MS;
    const frequency = (this.changeTimestamps.length / elapsedForRate) * 60_000;

    return {
      hand_position: position,
      gesture_frequency: round(frequency),
      assessment: assessGestures(frequency, position),
    };
  }

  reset(): void {
    this.history = [];
    this.lastPosition = null;
    this.changeTimestamps = [];
  }
}

function assessGestures(frequency: number, position: HandPosition): GestureAssessment {
  if (position === "crossed_arms") return "defensive";
  if (frequency > EXCESSIVE_THRESHOLD) return "excessive";
  if (frequency < TOO_STILL_THRESHOLD) return "too_still";
  return "natural";
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}
