import { beforeEach, describe, expect, it } from "vitest";

import { FACE, type Point3D } from "./landmarks";
import { computeHeadPose, HeadStabilityTracker } from "./headStability";

interface FacePoints {
  leftEye?: { x: number; y: number };
  rightEye?: { x: number; y: number };
  nose?: { x: number; y: number };
  forehead?: { x: number; y: number };
  chin?: { x: number; y: number };
}

function buildLandmarks(points: FacePoints = {}): Point3D[] {
  const landmarks: Point3D[] = new Array(478).fill(null).map(() => ({ x: 0, y: 0, z: 0 }));
  landmarks[FACE.LEFT_EYE_OUTER] = { x: -1, y: 0, z: 0, ...points.leftEye };
  landmarks[FACE.RIGHT_EYE_OUTER] = { x: 1, y: 0, z: 0, ...points.rightEye };
  landmarks[FACE.NOSE_TIP] = { x: 0, y: 0.5, z: 0, ...points.nose };
  landmarks[FACE.FOREHEAD] = { x: 0, y: -1, z: 0, ...points.forehead };
  landmarks[FACE.CHIN] = { x: 0, y: 1, z: 0, ...points.chin };
  return landmarks;
}

describe("computeHeadPose", () => {
  it("yaw increases as the nose shifts right of the eye midpoint", () => {
    const centered = computeHeadPose(buildLandmarks());
    const shiftedRight = computeHeadPose(buildLandmarks({ nose: { x: 0.6, y: 0.5 } }));
    expect(shiftedRight.yaw).toBeGreaterThan(centered.yaw);
  });

  it("yaw decreases as the nose shifts left of the eye midpoint", () => {
    const centered = computeHeadPose(buildLandmarks());
    const shiftedLeft = computeHeadPose(buildLandmarks({ nose: { x: -0.6, y: 0.5 } }));
    expect(shiftedLeft.yaw).toBeLessThan(centered.yaw);
  });

  it("pitch increases as the nose shifts down relative to the eye line", () => {
    const centered = computeHeadPose(buildLandmarks());
    const shiftedDown = computeHeadPose(buildLandmarks({ nose: { x: 0, y: 1.2 } }));
    expect(shiftedDown.pitch).toBeGreaterThan(centered.pitch);
  });

  it("roll is ~0 when the eyes are level", () => {
    const pose = computeHeadPose(buildLandmarks());
    expect(pose.roll).toBeCloseTo(0, 1);
  });

  it("roll reflects a tilted eye line", () => {
    const tilted = computeHeadPose(
      buildLandmarks({ leftEye: { x: -1, y: 0.5 }, rightEye: { x: 1, y: -0.5 } })
    );
    expect(Math.abs(tilted.roll)).toBeGreaterThan(10);
  });

  it("does not divide by zero when eyes are at the same point", () => {
    const pose = computeHeadPose(
      buildLandmarks({ leftEye: { x: 0, y: 0 }, rightEye: { x: 0, y: 0 } })
    );
    expect(Number.isFinite(pose.yaw)).toBe(true);
    expect(Number.isFinite(pose.roll)).toBe(true);
  });
});

describe("HeadStabilityTracker", () => {
  let tracker: HeadStabilityTracker;

  beforeEach(() => {
    tracker = new HeadStabilityTracker();
  });

  it("reports high stability for a perfectly still head", () => {
    let result;
    for (let t = 0; t <= 2000; t += 200) {
      result = tracker.processFrame(buildLandmarks(), t);
    }
    expect(result!.movement_pattern).toBe("stable");
    expect(result!.stability_score).toBeGreaterThan(0.9);
  });

  it("detects nodding when pitch oscillates while yaw/roll stay flat", () => {
    let result;
    for (let t = 0, i = 0; t <= 3000; t += 200, i++) {
      const noseY = i % 2 === 0 ? 0.5 : 3.0; // large, repeated vertical swing
      result = tracker.processFrame(buildLandmarks({ nose: { x: 0, y: noseY } }), t);
    }
    expect(result!.movement_pattern).toBe("nodding");
  });

  it("detects shaking when yaw oscillates while pitch/roll stay flat", () => {
    let result;
    for (let t = 0, i = 0; t <= 3000; t += 200, i++) {
      const noseX = i % 2 === 0 ? 0 : 3.0; // large, repeated horizontal swing
      result = tracker.processFrame(buildLandmarks({ nose: { x: noseX, y: 0.5 } }), t);
    }
    expect(result!.movement_pattern).toBe("shaking");
  });

  it("detects fidgeting when multiple axes are simultaneously noisy", () => {
    let result;
    for (let t = 0, i = 0; t <= 3000; t += 200, i++) {
      const wobble = i % 2 === 0 ? 0 : 2.5;
      result = tracker.processFrame(
        buildLandmarks({
          nose: { x: wobble, y: 0.5 + wobble },
          leftEye: { x: -1, y: wobble * 0.3 },
          rightEye: { x: 1, y: -wobble * 0.3 },
        }),
        t
      );
    }
    expect(result!.movement_pattern).toBe("fidgeting");
  });

  it("only considers the last 10 seconds of history", () => {
    tracker.processFrame(buildLandmarks({ nose: { x: 5, y: 5 } }), 0); // wild outlier, far in the past
    let result;
    for (let t = 11_000; t <= 13_000; t += 200) {
      result = tracker.processFrame(buildLandmarks(), t); // stable afterwards
    }
    expect(result!.movement_pattern).toBe("stable");
  });

  it("reset() clears history so stability recalculates from scratch", () => {
    for (let t = 0, i = 0; t <= 2000; t += 200, i++) {
      const noseX = i % 2 === 0 ? 0 : 3.0;
      tracker.processFrame(buildLandmarks({ nose: { x: noseX, y: 0.5 } }), t);
    }
    tracker.reset();

    const result = tracker.processFrame(buildLandmarks(), 3000);
    expect(result.stability_score).toBeGreaterThan(0.9);
  });
});
