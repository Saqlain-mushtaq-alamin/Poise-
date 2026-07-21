/**
 * Shared landmark types and index constants for MediaPipe Face Mesh (468
 * points, +10 more with iris refinement) and Pose (33 points). Every
 * analyzer in this directory (eyeContact, headStability, blinkDetector,
 * expressionClassifier, gestureAnalyzer) is pure math over these — none
 * of them touch MediaPipe, TensorFlow, or the camera directly. That's
 * what makes them fully unit-testable with synthetic coordinates in this
 * environment (no camera, no WASM runtime, no GPU) while still being the
 * real algorithm a live pipeline would run.
 */

export interface Point3D {
  x: number;
  y: number;
  z: number;
}

export interface PoseLandmark extends Point3D {
  visibility: number;
}

export type FaceLandmarks = Point3D[]; // indexed 0-467 (or 0-477 with iris refinement)
export type PoseLandmarks = PoseLandmark[]; // indexed 0-32

// ---- Face Mesh indices (standard MediaPipe topology) ----

export const FACE = {
  NOSE_TIP: 1,
  CHIN: 152,
  FOREHEAD: 10,
  LEFT_EYE_OUTER: 33, // subject's right eye, camera-left in a mirrored view
  RIGHT_EYE_OUTER: 263, // subject's left eye
  LEFT_MOUTH_CORNER: 61,
  RIGHT_MOUTH_CORNER: 291,
  UPPER_LIP_TOP: 13,
  LOWER_LIP_BOTTOM: 14,
  LEFT_EYEBROW_INNER: 55,
  RIGHT_EYEBROW_INNER: 285,
  // Iris centers, present only when Face Mesh is run with refineLandmarks.
  LEFT_IRIS_CENTER: 468,
  RIGHT_IRIS_CENTER: 473,
} as const;

// Six-point EAR landmark sets (Soukupová & Čech, 2016): [corner, top1, top2,
// corner, bottom1, bottom2].
export const RIGHT_EYE_EAR_POINTS = [33, 160, 158, 133, 153, 144] as const;
export const LEFT_EYE_EAR_POINTS = [362, 385, 387, 263, 373, 380] as const;

// Eye bounding box corners used for iris-ratio gaze estimation (outer
// corner, inner corner, upper lid, lower lid) per eye.
export const RIGHT_EYE_BOUNDS = { outer: 33, inner: 133, top: 159, bottom: 145 } as const;
export const LEFT_EYE_BOUNDS = { outer: 263, inner: 362, top: 386, bottom: 374 } as const;

// ---- Pose indices (BlazePose 33-point topology) ----

export const POSE = {
  NOSE: 0,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
} as const;

export function distance(a: Point3D, b: Point3D): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

export function midpoint(a: Point3D, b: Point3D): Point3D {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
}
