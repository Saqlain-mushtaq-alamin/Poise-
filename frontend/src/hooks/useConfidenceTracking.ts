import { useCallback, useRef, useState } from "react";

import type { PoiseAPI } from "../lib/api";
import type { ConfidenceFramePayload } from "../lib/types";
import { FaceAnalyzer, type FaceAnalysisResult } from "../services/vision/FaceAnalyzer";
import { ConfidenceCoach, type CoachingTip } from "../services/vision/confidenceCoach";
import { WebcamCapture } from "../services/vision/WebcamCapture";

interface UseConfidenceTrackingOptions {
  api: PoiseAPI | null;
  sessionId: string | null;
  /** Practice Mode shows coaching tips; Exam Mode never does — same rule
   * as Phase 5 spec §5.10. */
  coachingEnabled: boolean;
}

interface UseConfidenceTrackingResult {
  isTracking: boolean;
  latestResult: FaceAnalysisResult | null;
  coachingTip: CoachingTip | null;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
  dismissTip: () => void;
}

const FRAME_UPLOAD_BATCH_SIZE = 10;

function toPayload(result: FaceAnalysisResult): ConfidenceFramePayload {
  return {
    timestamp_ms: result.timestampMs,
    eye_contact: result.eyeContact,
    head_stability: result.headStability,
    blink_rate: result.blinkRate,
    expression: result.expression,
    gesture: result.gesture,
    composite_score: result.compositeScore,
  };
}

/**
 * This is orchestration glue over already-independently-tested pieces
 * (WebcamCapture, FaceAnalyzer, ConfidenceCoach) — see each of their own
 * test files. The real MediaPipe frame processing (`FaceAnalyzer.
 * processFrame`) isn't runnable in this environment (see that file's
 * docstring), so this hook's `start()` will throw when actually invoked
 * here; it's written against the real, intended integration shape rather
 * than mocked, matching Phase 3's `useVoicePipeline`.
 */
export function useConfidenceTracking({
  api,
  sessionId,
  coachingEnabled,
}: UseConfidenceTrackingOptions): UseConfidenceTrackingResult {
  const webcamRef = useRef<WebcamCapture | null>(null);
  const analyzerRef = useRef<FaceAnalyzer | null>(null);
  const coachRef = useRef<ConfidenceCoach | null>(null);
  const frameBufferRef = useRef<ConfidenceFramePayload[]>([]);
  const rafRef = useRef<number | null>(null);

  const [isTracking, setIsTracking] = useState(false);
  const [latestResult, setLatestResult] = useState<FaceAnalysisResult | null>(null);
  const [coachingTip, setCoachingTip] = useState<CoachingTip | null>(null);
  const [error, setError] = useState<string | null>(null);

  const getWebcam = useCallback(() => {
    if (!webcamRef.current) webcamRef.current = new WebcamCapture();
    return webcamRef.current;
  }, []);
  const getAnalyzer = useCallback(() => {
    if (!analyzerRef.current) analyzerRef.current = new FaceAnalyzer();
    return analyzerRef.current;
  }, []);
  const getCoach = useCallback(() => {
    if (!coachRef.current) coachRef.current = new ConfidenceCoach();
    return coachRef.current;
  }, []);

  const flushFrameBuffer = useCallback(async () => {
    if (!api || !sessionId || frameBufferRef.current.length === 0) return;
    const batch = frameBufferRef.current;
    frameBufferRef.current = [];
    try {
      await api.submitConfidenceFrames(sessionId, batch);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [api, sessionId]);

  const processLoop = useCallback(async () => {
    const webcam = getWebcam();
    const analyzer = getAnalyzer();
    const coach = getCoach();

    const frame = webcam.getFrame();
    if (frame) {
      try {
        const result = await analyzer.processFrame(frame, Date.now());
        if (result) {
          setLatestResult(result);
          frameBufferRef.current.push(toPayload(result));
          if (frameBufferRef.current.length >= FRAME_UPLOAD_BATCH_SIZE) {
            void flushFrameBuffer();
          }

          if (coachingEnabled) {
            const tip = coach.analyzeTrend({
              timestampMs: result.timestampMs,
              eyeContactRatio: result.eyeContact.contact_ratio_30s,
              stabilityScore: result.headStability.stability_score,
              expression: result.expression,
              blinksPerMinute: result.blinkRate.blinks_per_minute,
              gestureAssessment: result.gesture?.assessment,
            });
            if (tip) setCoachingTip(tip);
          }
        }
      } catch (err) {
        setError((err as Error).message);
      }
    }

    rafRef.current = requestAnimationFrame(() => void processLoop());
  }, [coachingEnabled, flushFrameBuffer, getAnalyzer, getCoach, getWebcam]);

  const start = useCallback(async () => {
    setError(null);
    try {
      await getWebcam().start();
      setIsTracking(true);
      rafRef.current = requestAnimationFrame(() => void processLoop());
    } catch (err) {
      setError((err as Error).message);
    }
  }, [getWebcam, processLoop]);

  const stop = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    getWebcam().stop();
    getAnalyzer().reset();
    getCoach().reset();
    void flushFrameBuffer();
    setIsTracking(false);
    setLatestResult(null);
  }, [flushFrameBuffer, getAnalyzer, getCoach, getWebcam]);

  const dismissTip = useCallback(() => setCoachingTip(null), []);

  return { isTracking, latestResult, coachingTip, error, start, stop, dismissTip };
}
