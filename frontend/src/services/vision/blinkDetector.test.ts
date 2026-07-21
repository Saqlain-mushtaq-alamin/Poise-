import { beforeEach, describe, expect, it } from "vitest";

import { assessBlinkRate, BlinkDetector, computeEAR, EAR_BLINK_THRESHOLD } from "./blinkDetector";
import { LEFT_EYE_EAR_POINTS, RIGHT_EYE_EAR_POINTS, type Point3D } from "./landmarks";

function eyeLandmarks(points: readonly number[], open: boolean): Point3D[] {
  const landmarks: Point3D[] = new Array(478).fill(null).map(() => ({ x: 0, y: 0, z: 0 }));
  const [corner1, top1, top2, corner2, bottom1, bottom2] = points;
  landmarks[corner1] = { x: 0, y: 0.5, z: 0 };
  landmarks[corner2] = { x: 1, y: 0.5, z: 0 };
  if (open) {
    landmarks[top1] = { x: 0.3, y: 0.35, z: 0 };
    landmarks[bottom2] = { x: 0.3, y: 0.65, z: 0 };
    landmarks[top2] = { x: 0.7, y: 0.35, z: 0 };
    landmarks[bottom1] = { x: 0.7, y: 0.65, z: 0 };
  } else {
    landmarks[top1] = { x: 0.3, y: 0.5, z: 0 };
    landmarks[bottom2] = { x: 0.3, y: 0.5, z: 0 };
    landmarks[top2] = { x: 0.7, y: 0.5, z: 0 };
    landmarks[bottom1] = { x: 0.7, y: 0.5, z: 0 };
  }
  return landmarks;
}

function bothEyesLandmarks(open: boolean): Point3D[] {
  const right = eyeLandmarks(RIGHT_EYE_EAR_POINTS, open);
  const left = eyeLandmarks(LEFT_EYE_EAR_POINTS, open);
  const combined = right.slice();
  LEFT_EYE_EAR_POINTS.forEach((idx) => {
    combined[idx] = left[idx];
  });
  return combined;
}

describe("computeEAR", () => {
  it("returns a high EAR (~0.3) for an open eye", () => {
    const landmarks = eyeLandmarks(RIGHT_EYE_EAR_POINTS, true);
    const ear = computeEAR(landmarks, RIGHT_EYE_EAR_POINTS);
    expect(ear).toBeCloseTo(0.3, 5);
  });

  it("returns ~0 for a fully closed eye", () => {
    const landmarks = eyeLandmarks(RIGHT_EYE_EAR_POINTS, false);
    const ear = computeEAR(landmarks, RIGHT_EYE_EAR_POINTS);
    expect(ear).toBeCloseTo(0, 5);
  });

  it("open eye EAR is above the blink threshold", () => {
    const landmarks = eyeLandmarks(RIGHT_EYE_EAR_POINTS, true);
    expect(computeEAR(landmarks, RIGHT_EYE_EAR_POINTS)).toBeGreaterThan(EAR_BLINK_THRESHOLD);
  });

  it("closed eye EAR is below the blink threshold", () => {
    const landmarks = eyeLandmarks(RIGHT_EYE_EAR_POINTS, false);
    expect(computeEAR(landmarks, RIGHT_EYE_EAR_POINTS)).toBeLessThan(EAR_BLINK_THRESHOLD);
  });

  it("handles a zero-width eye (horizontal distance 0) without dividing by zero", () => {
    const landmarks: Point3D[] = new Array(478).fill({ x: 0, y: 0, z: 0 });
    const points = RIGHT_EYE_EAR_POINTS;
    landmarks[points[0]] = { x: 0.5, y: 0.5, z: 0 };
    landmarks[points[3]] = { x: 0.5, y: 0.5, z: 0 }; // same point -> 0 horizontal distance
    expect(computeEAR(landmarks, points)).toBe(0);
  });
});

describe("assessBlinkRate", () => {
  it("classifies normal range (10-25/min)", () => {
    expect(assessBlinkRate(16)).toBe("normal");
  });

  it("classifies elevated (>25/min, stressed)", () => {
    expect(assessBlinkRate(30)).toBe("elevated");
  });

  it("classifies low (<10/min, zoned out)", () => {
    expect(assessBlinkRate(5)).toBe("low");
  });

  it("boundary at exactly 25 is still normal", () => {
    expect(assessBlinkRate(25)).toBe("normal");
  });

  it("boundary at exactly 10 is still normal", () => {
    expect(assessBlinkRate(10)).toBe("normal");
  });
});

describe("BlinkDetector", () => {
  let detector: BlinkDetector;

  beforeEach(() => {
    detector = new BlinkDetector();
  });

  it("does not confirm a blink while the eye stays open", () => {
    const result = detector.processFrame(bothEyesLandmarks(true), 0);
    expect(result.is_blinking).toBe(false);
    expect(result.blinks_per_minute).toBe(0);
  });

  it("reports is_blinking true while EAR is below threshold", () => {
    detector.processFrame(bothEyesLandmarks(true), 0);
    const result = detector.processFrame(bothEyesLandmarks(false), 33);
    expect(result.is_blinking).toBe(true);
  });

  it("confirms a genuine blink (150ms closure) and counts it", () => {
    detector.processFrame(bothEyesLandmarks(true), 0);
    detector.processFrame(bothEyesLandmarks(false), 100); // eye closes
    const result = detector.processFrame(bothEyesLandmarks(true), 250); // eye reopens, 150ms later

    expect(result.is_blinking).toBe(false);
    expect(result.blinks_per_minute).toBeGreaterThan(0);
  });

  it("does not count a closure shorter than 100ms as a blink", () => {
    detector.processFrame(bothEyesLandmarks(true), 0);
    detector.processFrame(bothEyesLandmarks(false), 100);
    const result = detector.processFrame(bothEyesLandmarks(true), 150); // only 50ms closure

    expect(result.blinks_per_minute).toBe(0);
  });

  it("does not count a closure longer than 400ms as a blink (deliberate eye-close)", () => {
    detector.processFrame(bothEyesLandmarks(true), 0);
    detector.processFrame(bothEyesLandmarks(false), 100);
    const result = detector.processFrame(bothEyesLandmarks(true), 600); // 500ms closure

    expect(result.blinks_per_minute).toBe(0);
  });

  it("accumulates multiple blinks into a plausible per-minute rate", () => {
    let t = 0;
    detector.processFrame(bothEyesLandmarks(true), t);
    for (let i = 0; i < 5; i++) {
      t += 1000;
      detector.processFrame(bothEyesLandmarks(false), t);
      t += 150;
      detector.processFrame(bothEyesLandmarks(true), t);
    }
    const result = detector.processFrame(bothEyesLandmarks(true), t + 1);
    expect(result.blinks_per_minute).toBeGreaterThan(0);
  });

  it("reset() clears blink history", () => {
    detector.processFrame(bothEyesLandmarks(true), 0);
    detector.processFrame(bothEyesLandmarks(false), 100);
    detector.processFrame(bothEyesLandmarks(true), 250);

    detector.reset();
    const result = detector.processFrame(bothEyesLandmarks(true), 300);
    expect(result.blinks_per_minute).toBe(0);
    expect(result.is_blinking).toBe(false);
  });
});
