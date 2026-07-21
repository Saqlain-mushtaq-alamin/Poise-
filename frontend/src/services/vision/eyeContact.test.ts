import { beforeEach, describe, expect, it } from "vitest";

import { EyeContactAnalyzer } from "./eyeContact";
import { FACE, LEFT_EYE_BOUNDS, type Point3D, RIGHT_EYE_BOUNDS } from "./landmarks";

function buildLandmarks(ratioH: number, ratioV: number): Point3D[] {
  const landmarks: Point3D[] = new Array(478).fill(null).map(() => ({ x: 0, y: 0, z: 0 }));
  const setEye = (
    bounds: { outer: number; inner: number; top: number; bottom: number },
    iris: number
  ) => {
    landmarks[bounds.outer] = { x: 0, y: 0, z: 0 };
    landmarks[bounds.inner] = { x: 1, y: 0, z: 0 };
    landmarks[bounds.top] = { x: 0, y: 0, z: 0 };
    landmarks[bounds.bottom] = { x: 0, y: 1, z: 0 };
    landmarks[iris] = { x: ratioH, y: ratioV, z: 0 };
  };
  setEye(RIGHT_EYE_BOUNDS, FACE.RIGHT_IRIS_CENTER);
  setEye(LEFT_EYE_BOUNDS, FACE.LEFT_IRIS_CENTER);
  return landmarks;
}

describe("EyeContactAnalyzer", () => {
  let analyzer: EyeContactAnalyzer;

  beforeEach(() => {
    analyzer = new EyeContactAnalyzer();
  });

  it("classifies centered iris as direct eye contact", () => {
    const result = analyzer.processFrame(buildLandmarks(0.5, 0.5), 0);
    expect(result.direction).toBe("direct");
    expect(result.confidence).toBeGreaterThan(0.9);
  });

  it("classifies iris shifted left as away_left", () => {
    const result = analyzer.processFrame(buildLandmarks(0.2, 0.5), 0);
    expect(result.direction).toBe("away_left");
  });

  it("classifies iris shifted right as away_right", () => {
    const result = analyzer.processFrame(buildLandmarks(0.8, 0.5), 0);
    expect(result.direction).toBe("away_right");
  });

  it("classifies iris shifted up as up", () => {
    const result = analyzer.processFrame(buildLandmarks(0.5, 0.2), 0);
    expect(result.direction).toBe("up");
  });

  it("classifies iris shifted down as down", () => {
    const result = analyzer.processFrame(buildLandmarks(0.5, 0.8), 0);
    expect(result.direction).toBe("down");
  });

  it("small deviations within tolerance are still direct", () => {
    const result = analyzer.processFrame(buildLandmarks(0.55, 0.48), 0);
    expect(result.direction).toBe("direct");
  });

  it("contact_ratio_30s is 1.0 when every frame in the window is direct", () => {
    analyzer.processFrame(buildLandmarks(0.5, 0.5), 0);
    analyzer.processFrame(buildLandmarks(0.5, 0.5), 1000);
    const result = analyzer.processFrame(buildLandmarks(0.5, 0.5), 2000);
    expect(result.contact_ratio_30s).toBe(1.0);
  });

  it("contact_ratio_30s reflects a mix of direct and away frames", () => {
    analyzer.processFrame(buildLandmarks(0.5, 0.5), 0); // direct
    analyzer.processFrame(buildLandmarks(0.2, 0.5), 1000); // away
    const result = analyzer.processFrame(buildLandmarks(0.5, 0.5), 2000); // direct
    expect(result.contact_ratio_30s).toBeCloseTo(2 / 3, 2);
  });

  it("old frames outside the 30s window are excluded from the ratio", () => {
    analyzer.processFrame(buildLandmarks(0.2, 0.5), 0); // away, will age out
    analyzer.processFrame(buildLandmarks(0.5, 0.5), 31_000); // direct, now the only frame in-window
    const result = analyzer.processFrame(buildLandmarks(0.5, 0.5), 32_000);
    expect(result.contact_ratio_30s).toBe(1.0);
  });

  it("reset() clears the rolling window", () => {
    analyzer.processFrame(buildLandmarks(0.5, 0.5), 0);
    analyzer.processFrame(buildLandmarks(0.5, 0.5), 1000);
    analyzer.reset();

    const result = analyzer.processFrame(buildLandmarks(0.2, 0.5), 2000);
    expect(result.contact_ratio_30s).toBe(0); // only the (away) frame after reset counts
  });

  it("confidence decreases the further the gaze drifts from center", () => {
    const slightlyOff = analyzer.processFrame(buildLandmarks(0.35, 0.5), 0);
    analyzer.reset();
    const veryOff = analyzer.processFrame(buildLandmarks(0.0, 0.5), 0);
    expect(veryOff.confidence).toBeGreaterThan(slightlyOff.confidence);
  });
});
