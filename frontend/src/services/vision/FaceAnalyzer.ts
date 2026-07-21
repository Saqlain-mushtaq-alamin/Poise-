/**
 * Orchestrates every analyzer in this directory into one confidence
 * analysis per frame, per Phase 5 spec §5.2.
 *
 * `analyzeLandmarks` is the real, fully-tested core: given already-
 * extracted Face Mesh / Pose landmarks (from MediaPipe, or a test
 * fixture — the method doesn't care which), it runs eye contact, head
 * stability, blink detection, expression classification, and gesture
 * analysis, then combines them into a composite score. That's all pure
 * TypeScript with zero CV/ML runtime dependency, which is why it's
 * thoroughly unit tested here despite this environment having no camera.
 *
 * `processFrame` is the actual MediaPipe integration — lazy-loading
 * `@mediapipe/face_mesh` and `@mediapipe/pose`, running them over a raw
 * video frame. That part genuinely needs a browser with WebGL/WASM and,
 * for the models themselves, a network route this environment doesn't
 * have. It's written to the real MediaPipe API surface but is NOT
 * exercised by any test — see FaceAnalyzer.test.ts, which tests
 * `analyzeLandmarks` exclusively.
 */
import { BlinkDetector, type BlinkSignal } from "./blinkDetector";
import { computeCompositeScore } from "./confidenceScorer";
import { classifyExpression, type Expression } from "./expressionClassifier";
import { EyeContactAnalyzer, type EyeContactSignal } from "./eyeContact";
import { GestureAnalyzer, type GestureSignal } from "./gestureAnalyzer";
import { HeadStabilityTracker, type HeadStabilitySignal } from "./headStability";
import type { FaceLandmarks, PoseLandmarks } from "./landmarks";

export interface FaceAnalysisResult {
  eyeContact: EyeContactSignal;
  headStability: HeadStabilitySignal;
  blinkRate: BlinkSignal;
  expression: Expression;
  gesture?: GestureSignal;
  compositeScore: number;
  timestampMs: number;
}

export class FaceAnalyzer {
  private eyeContactAnalyzer = new EyeContactAnalyzer();
  private headStabilityTracker = new HeadStabilityTracker();
  private blinkDetector = new BlinkDetector();
  private gestureAnalyzer = new GestureAnalyzer();

  /** The real, tested orchestration — combines already-extracted
   * landmarks into one full confidence analysis. `poseLandmarks` is
   * optional: gesture analysis (and its weight in the composite score)
   * is skipped gracefully when pose tracking isn't running. */
  analyzeLandmarks(
    faceLandmarks: FaceLandmarks,
    poseLandmarks: PoseLandmarks | null,
    timestampMs: number
  ): FaceAnalysisResult {
    const eyeContact = this.eyeContactAnalyzer.processFrame(faceLandmarks, timestampMs);
    const headStability = this.headStabilityTracker.processFrame(faceLandmarks, timestampMs);
    const blinkRate = this.blinkDetector.processFrame(faceLandmarks, timestampMs);
    const { expression } = classifyExpression(faceLandmarks, {
      avgEar: (blinkRate.ear_left + blinkRate.ear_right) / 2,
      blinksPerMinute: blinkRate.blinks_per_minute,
    });
    const gesture = poseLandmarks
      ? this.gestureAnalyzer.processFrame(poseLandmarks, timestampMs)
      : undefined;

    const compositeScore = computeCompositeScore({
      eyeContactRatio: eyeContact.contact_ratio_30s,
      stabilityScore: headStability.stability_score,
      blinkAssessment: blinkRate.assessment,
      expression,
      gestureAssessment: gesture?.assessment,
      gazeDirection: eyeContact.direction,
    });

    return {
      eyeContact,
      headStability,
      blinkRate,
      expression,
      gesture,
      compositeScore,
      timestampMs,
    };
  }

  reset(): void {
    this.eyeContactAnalyzer.reset();
    this.headStabilityTracker.reset();
    this.blinkDetector.reset();
    this.gestureAnalyzer.reset();
  }

  /** Real MediaPipe integration — see the module docstring for why this
   * isn't exercised by any test in this build. Returns null when no face
   * is detected (per the spec's "graceful handling" acceptance
   * criterion) rather than throwing, so a caller's render loop can just
   * skip the frame. */
  async processFrame(
    _imageData: ImageData,
    _timestampMs: number
  ): Promise<FaceAnalysisResult | null> {
    throw new Error(
      "MediaPipe Face Mesh/Pose integration is not available in this build. " +
        "See FaceAnalyzer.ts's module docstring — analyzeLandmarks() is the tested, " +
        "camera-independent entry point; wire a real MediaPipe result into it."
    );
  }
}
