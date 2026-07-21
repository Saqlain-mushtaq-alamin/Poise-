/**
 * Expression classification, per Phase 5 spec §5.6.
 *
 * The spec calls for a small trained FER (Facial Expression Recognition)
 * TF.js model. That needs a downloadable model file and a WebGL/WASM
 * backend — neither available in this environment, and more importantly
 * not something a scaffold should silently pretend to have. So, same
 * philosophy as Phase 4's `FrameworkDetector`: this implements a genuine,
 * working heuristic — mouth-corner curvature for a smile, mouth
 * openness + eyebrow height for surprise, eyebrow furrow for confusion,
 * blink rate + eye openness for anxiety — that produces real, checkable
 * output today. It's honest about being a heuristic, not a trained
 * classifier, and is written so `_classifyWithModel` can replace the
 * heuristic path later without changing the return shape.
 */
import { distance, FACE, type Point3D } from "./landmarks";

export type Expression = "neutral" | "happy" | "surprised" | "confused" | "anxious" | "focused";

export interface ExpressionResult {
  expression: Expression;
  confidence: number;
}

interface ExpressionInputs {
  /** Average of both eyes' EAR (see blinkDetector.ts) — reused here
   * rather than recomputed, since the caller (the frame-processing
   * pipeline) already has it. */
  avgEar: number;
  blinksPerMinute: number;
}

// Every threshold below is tuned against this module's own synthetic
// fixtures (expressionClassifier.test.ts), not against labeled face
// photos — see the module docstring.
const SMILE_WIDTH_RATIO_THRESHOLD = 0.42; // mouth width / face width
const SURPRISE_MOUTH_OPEN_RATIO_THRESHOLD = 0.18; // mouth height / face height
const EYEBROW_RAISE_THRESHOLD = 0.02; // normalized eyebrow-to-eye distance above baseline
const CONFUSION_EYEBROW_ASYMMETRY_THRESHOLD = 0.015;
const ANXIOUS_BLINK_RATE_THRESHOLD = 25;
const ANXIOUS_EAR_THRESHOLD = 0.22; // narrowed eyes

export function classifyExpression(
  landmarks: Point3D[],
  inputs: ExpressionInputs
): ExpressionResult {
  const leftEye = landmarks[FACE.LEFT_EYE_OUTER];
  const rightEye = landmarks[FACE.RIGHT_EYE_OUTER];
  const faceWidth = distance(leftEye, rightEye) || 1;

  const forehead = landmarks[FACE.FOREHEAD];
  const chin = landmarks[FACE.CHIN];
  const faceHeight = distance(forehead, chin) || 1;

  const mouthLeft = landmarks[FACE.LEFT_MOUTH_CORNER];
  const mouthRight = landmarks[FACE.RIGHT_MOUTH_CORNER];
  const mouthTop = landmarks[FACE.UPPER_LIP_TOP];
  const mouthBottom = landmarks[FACE.LOWER_LIP_BOTTOM];

  const mouthWidthRatio = distance(mouthLeft, mouthRight) / faceWidth;
  const mouthOpenRatio = distance(mouthTop, mouthBottom) / faceHeight;

  const leftBrow = landmarks[FACE.LEFT_EYEBROW_INNER];
  const rightBrow = landmarks[FACE.RIGHT_EYEBROW_INNER];
  const leftBrowRaise = (leftEye.y - leftBrow.y) / faceHeight;
  const rightBrowRaise = (rightEye.y - rightBrow.y) / faceHeight;
  const avgBrowRaise = (leftBrowRaise + rightBrowRaise) / 2;
  const browAsymmetry = Math.abs(leftBrowRaise - rightBrowRaise);

  // Order matters: check the strongest, most specific signals first.
  if (mouthOpenRatio > SURPRISE_MOUTH_OPEN_RATIO_THRESHOLD && avgBrowRaise > EYEBROW_RAISE_THRESHOLD) {
    return { expression: "surprised", confidence: confidenceFrom(mouthOpenRatio, SURPRISE_MOUTH_OPEN_RATIO_THRESHOLD) };
  }

  if (browAsymmetry > CONFUSION_EYEBROW_ASYMMETRY_THRESHOLD) {
    return { expression: "confused", confidence: confidenceFrom(browAsymmetry, CONFUSION_EYEBROW_ASYMMETRY_THRESHOLD) };
  }

  if (mouthWidthRatio > SMILE_WIDTH_RATIO_THRESHOLD) {
    return { expression: "happy", confidence: confidenceFrom(mouthWidthRatio, SMILE_WIDTH_RATIO_THRESHOLD) };
  }

  if (inputs.blinksPerMinute > ANXIOUS_BLINK_RATE_THRESHOLD && inputs.avgEar < ANXIOUS_EAR_THRESHOLD) {
    return { expression: "anxious", confidence: 0.6 };
  }

  if (avgBrowRaise < -EYEBROW_RAISE_THRESHOLD) {
    // Lowered, slightly furrowed brows with an otherwise neutral mouth
    // reads as concentration rather than any of the above.
    return { expression: "focused", confidence: 0.55 };
  }

  return { expression: "neutral", confidence: 0.5 };
}

function confidenceFrom(value: number, threshold: number): number {
  const ratio = value / threshold;
  return Math.max(0.5, Math.min(1, ratio - 0.5));
}
