/**
 * Composite confidence score (0-100), per Phase 5 spec §5.7's
 * `ConfidenceFrame.composite_score`. A single weighted blend of every
 * signal this module produces — pure arithmetic, no CV/ML dependency.
 */
import type { BlinkSignal } from "./blinkDetector";
import type { GazeDirection } from "./eyeContact";
import type { Expression } from "./expressionClassifier";
import type { GestureAssessment } from "./gestureAnalyzer";

export interface CompositeScoreInputs {
  eyeContactRatio: number; // 0-1
  stabilityScore: number; // 0-1
  blinkAssessment: BlinkSignal["assessment"];
  expression: Expression;
  gestureAssessment?: GestureAssessment;
  gazeDirection: GazeDirection;
}

// Weights sum to 1.0 across whichever signals are present; gesture is
// optional (pose tracking may not always be running) and its weight is
// redistributed proportionally to the other signals when absent, rather
// than silently scoring gesture-less sessions lower across the board.
const WEIGHTS = {
  eyeContact: 0.35,
  stability: 0.25,
  blink: 0.15,
  expression: 0.15,
  gesture: 0.1,
};

const EXPRESSION_SCORE: Record<Expression, number> = {
  happy: 1.0,
  focused: 0.9,
  neutral: 0.75,
  surprised: 0.6,
  confused: 0.4,
  anxious: 0.25,
};

const BLINK_SCORE: Record<BlinkSignal["assessment"], number> = {
  normal: 1.0,
  elevated: 0.5,
  low: 0.6,
};

const GESTURE_SCORE: Record<GestureAssessment, number> = {
  natural: 1.0,
  too_still: 0.7,
  excessive: 0.4,
  defensive: 0.3,
};

export function computeCompositeScore(inputs: CompositeScoreInputs): number {
  const components: { weight: number; score: number }[] = [
    { weight: WEIGHTS.eyeContact, score: inputs.eyeContactRatio },
    { weight: WEIGHTS.stability, score: inputs.stabilityScore },
    { weight: WEIGHTS.blink, score: BLINK_SCORE[inputs.blinkAssessment] },
    { weight: WEIGHTS.expression, score: EXPRESSION_SCORE[inputs.expression] },
  ];

  if (inputs.gestureAssessment) {
    components.push({ weight: WEIGHTS.gesture, score: GESTURE_SCORE[inputs.gestureAssessment] });
  }

  const totalWeight = components.reduce((sum, c) => sum + c.weight, 0);
  const weightedSum = components.reduce((sum, c) => sum + c.weight * c.score, 0);
  const normalizedScore = totalWeight > 0 ? weightedSum / totalWeight : 0;

  return Math.round(clamp01(normalizedScore) * 100);
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}
