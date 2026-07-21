import { beforeEach, describe, expect, it } from "vitest";

import { FaceAnalyzer } from "./FaceAnalyzer";
import {
  FACE,
  LEFT_EYE_BOUNDS,
  LEFT_EYE_EAR_POINTS,
  POSE,
  type Point3D,
  type PoseLandmarks,
  RIGHT_EYE_BOUNDS,
  RIGHT_EYE_EAR_POINTS,
} from "./landmarks";

function buildFaceLandmarks(): Point3D[] {
  const l: Point3D[] = new Array(478).fill(null).map(() => ({ x: 0, y: 0, z: 0 }));

  // One coherent, level, centered face. Every index below is set exactly
  // once — MediaPipe's real topology reuses eye-corner landmarks across
  // head-pose, gaze-ratio, and EAR calculations, so (unlike most of this
  // module's other test files, which analyze one sub-region in
  // isolation) this fixture has to satisfy all of them simultaneously.

  // Head pose reference points.
  l[FACE.NOSE_TIP] = { x: 0, y: 0, z: 0 };
  l[FACE.FOREHEAD] = { x: 0, y: -1.5, z: 0 };
  l[FACE.CHIN] = { x: 0, y: 1.5, z: 0 };

  // Right eye (subject's right / image-left): outer=33, inner=133.
  l[FACE.LEFT_EYE_OUTER] = { x: -1, y: -0.5, z: 0 }; // == RIGHT_EYE_BOUNDS.outer (33)
  l[RIGHT_EYE_BOUNDS.inner] = { x: -0.4, y: -0.5, z: 0 };
  l[RIGHT_EYE_BOUNDS.top] = { x: -0.7, y: -0.6, z: 0 };
  l[RIGHT_EYE_BOUNDS.bottom] = { x: -0.7, y: -0.4, z: 0 };
  l[FACE.RIGHT_IRIS_CENTER] = { x: -0.7, y: -0.5, z: 0 }; // centered -> direct gaze

  // Left eye (subject's left / image-right): inner=362, outer=263.
  l[FACE.RIGHT_EYE_OUTER] = { x: 1, y: -0.5, z: 0 }; // == LEFT_EYE_BOUNDS.outer (263)
  l[LEFT_EYE_BOUNDS.inner] = { x: 0.4, y: -0.5, z: 0 };
  l[LEFT_EYE_BOUNDS.top] = { x: 0.7, y: -0.6, z: 0 };
  l[LEFT_EYE_BOUNDS.bottom] = { x: 0.7, y: -0.4, z: 0 };
  l[FACE.LEFT_IRIS_CENTER] = { x: 0.7, y: -0.5, z: 0 }; // centered -> direct gaze

  // EAR points for an open eye (~0.3), sharing the same corner landmarks
  // as the gaze bounds above.
  l[RIGHT_EYE_EAR_POINTS[1]] = { x: -0.7, y: -0.59, z: 0 }; // top1 (160)
  l[RIGHT_EYE_EAR_POINTS[2]] = { x: -0.55, y: -0.59, z: 0 }; // top2 (158)
  l[RIGHT_EYE_EAR_POINTS[4]] = { x: -0.55, y: -0.41, z: 0 }; // bottom1 (153)
  l[RIGHT_EYE_EAR_POINTS[5]] = { x: -0.7, y: -0.41, z: 0 }; // bottom2 (144)

  l[LEFT_EYE_EAR_POINTS[1]] = { x: 0.55, y: -0.59, z: 0 }; // top1 (385)
  l[LEFT_EYE_EAR_POINTS[2]] = { x: 0.85, y: -0.59, z: 0 }; // top2 (387)
  l[LEFT_EYE_EAR_POINTS[4]] = { x: 0.85, y: -0.41, z: 0 }; // bottom1 (373)
  l[LEFT_EYE_EAR_POINTS[5]] = { x: 0.55, y: -0.41, z: 0 }; // bottom2 (380)

  // Mouth: narrow enough to stay under the smile-width threshold, closed
  // enough to stay under the surprise mouth-open threshold.
  l[FACE.LEFT_MOUTH_CORNER] = { x: -0.3, y: 0.5, z: 0 };
  l[FACE.RIGHT_MOUTH_CORNER] = { x: 0.3, y: 0.5, z: 0 };
  l[FACE.UPPER_LIP_TOP] = { x: 0, y: 0.45, z: 0 };
  l[FACE.LOWER_LIP_BOTTOM] = { x: 0, y: 0.55, z: 0 };

  // Eyebrows level with their respective eyes -> zero raise, zero asymmetry.
  l[FACE.LEFT_EYEBROW_INNER] = { x: -1, y: -0.5, z: 0 };
  l[FACE.RIGHT_EYEBROW_INNER] = { x: 1, y: -0.5, z: 0 };

  return l;
}

function buildPoseLandmarks(): PoseLandmarks {
  const p: PoseLandmarks = new Array(33).fill(null).map(() => ({ x: 0, y: 0, z: 0, visibility: 1 }));
  p[POSE.NOSE] = { x: 0, y: -1, z: 0, visibility: 1 };
  p[POSE.LEFT_SHOULDER] = { x: -1, y: 0, z: 0, visibility: 1 };
  p[POSE.RIGHT_SHOULDER] = { x: 1, y: 0, z: 0, visibility: 1 };
  p[POSE.LEFT_HIP] = { x: -1, y: 2, z: 0, visibility: 1 };
  p[POSE.RIGHT_HIP] = { x: 1, y: 2, z: 0, visibility: 1 };
  p[POSE.LEFT_WRIST] = { x: -1, y: 2, z: 0, visibility: 1 };
  p[POSE.RIGHT_WRIST] = { x: 1, y: 2, z: 0, visibility: 1 };
  return p;
}

describe("FaceAnalyzer.analyzeLandmarks", () => {
  let analyzer: FaceAnalyzer;

  beforeEach(() => {
    analyzer = new FaceAnalyzer();
  });

  it("combines every sub-analyzer into one result", () => {
    const result = analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 0);

    expect(result.eyeContact.direction).toBe("direct");
    expect(result.headStability.movement_pattern).toBe("stable");
    expect(result.blinkRate.is_blinking).toBe(false);
    expect(result.expression).toBe("neutral");
    expect(result.gesture?.hand_position).toBe("resting");
    expect(result.compositeScore).toBeGreaterThan(0);
    expect(result.timestampMs).toBe(0);
  });

  it("a confident, well-behaved frame scores highly", () => {
    const result = analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 0);
    expect(result.compositeScore).toBeGreaterThan(70);
  });

  it("gesture is undefined when no pose landmarks are provided", () => {
    const result = analyzer.analyzeLandmarks(buildFaceLandmarks(), null, 0);
    expect(result.gesture).toBeUndefined();
  });

  it("composite score is still computed without pose landmarks", () => {
    const result = analyzer.analyzeLandmarks(buildFaceLandmarks(), null, 0);
    expect(result.compositeScore).toBeGreaterThan(0);
  });

  it("maintains rolling state across multiple frames (eye contact ratio accumulates)", () => {
    analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 0);
    analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 1000);
    const result = analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 2000);
    expect(result.eyeContact.contact_ratio_30s).toBe(1.0);
  });

  it("reset() clears state in every sub-analyzer", () => {
    analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 0);
    analyzer.reset();

    // A fresh analyzer and a reset analyzer should behave identically on
    // the same input.
    const fresh = new FaceAnalyzer().analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 0);
    const afterReset = analyzer.analyzeLandmarks(buildFaceLandmarks(), buildPoseLandmarks(), 0);
    expect(afterReset.eyeContact.contact_ratio_30s).toBe(fresh.eyeContact.contact_ratio_30s);
  });
});

describe("FaceAnalyzer.processFrame", () => {
  it("is written against the real MediaPipe API surface but not runnable in this environment", async () => {
    const analyzer = new FaceAnalyzer();
    const fakeImageData = { data: new Uint8ClampedArray(4), width: 1, height: 1 } as ImageData;
    await expect(analyzer.processFrame(fakeImageData, 0)).rejects.toThrow(
      /MediaPipe.*not available/
    );
  });
});
