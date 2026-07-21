import { beforeEach, describe, expect, it } from "vitest";

import { GestureAnalyzer } from "./gestureAnalyzer";
import { POSE, type PoseLandmarks } from "./landmarks";

interface PosePoints {
  leftWrist?: { x: number; y: number };
  rightWrist?: { x: number; y: number };
}

function buildPose(points: PosePoints = {}): PoseLandmarks {
  const pose: PoseLandmarks = new Array(33)
    .fill(null)
    .map(() => ({ x: 0, y: 0, z: 0, visibility: 1 }));

  pose[POSE.NOSE] = { x: 0, y: -1, z: 0, visibility: 1 };
  pose[POSE.LEFT_SHOULDER] = { x: -1, y: 0, z: 0, visibility: 1 };
  pose[POSE.RIGHT_SHOULDER] = { x: 1, y: 0, z: 0, visibility: 1 };
  pose[POSE.LEFT_ELBOW] = { x: -1, y: 1, z: 0, visibility: 1 };
  pose[POSE.RIGHT_ELBOW] = { x: 1, y: 1, z: 0, visibility: 1 };
  pose[POSE.LEFT_HIP] = { x: -1, y: 2, z: 0, visibility: 1 };
  pose[POSE.RIGHT_HIP] = { x: 1, y: 2, z: 0, visibility: 1 };
  // Default: both wrists resting near the hips.
  pose[POSE.LEFT_WRIST] = { x: -1, y: 2, z: 0, visibility: 1, ...points.leftWrist };
  pose[POSE.RIGHT_WRIST] = { x: 1, y: 2, z: 0, visibility: 1, ...points.rightWrist };

  return pose;
}

describe("GestureAnalyzer classification", () => {
  let analyzer: GestureAnalyzer;

  beforeEach(() => {
    analyzer = new GestureAnalyzer();
  });

  it("classifies wrists near the hips as resting", () => {
    const result = analyzer.processFrame(buildPose(), 0);
    expect(result.hand_position).toBe("resting");
  });

  it("classifies a wrist near the nose as face_touching", () => {
    const result = analyzer.processFrame(
      buildPose({ leftWrist: { x: 0, y: -1 } }),
      0
    );
    expect(result.hand_position).toBe("face_touching");
  });

  it("classifies wrists crossed to opposite shoulders as crossed_arms", () => {
    const result = analyzer.processFrame(
      buildPose({ leftWrist: { x: 1, y: 0 }, rightWrist: { x: -1, y: 0 } }),
      0
    );
    expect(result.hand_position).toBe("crossed_arms");
  });

  it("classifies a raised hand (above shoulder height) as gesturing", () => {
    const result = analyzer.processFrame(
      buildPose({ leftWrist: { x: -2, y: -1 } }),
      0
    );
    expect(result.hand_position).toBe("gesturing");
  });

  it("classifies an ambiguous mid-level position as fidgeting", () => {
    const result = analyzer.processFrame(
      buildPose({ leftWrist: { x: -3, y: 0.5 }, rightWrist: { x: 3, y: 0.5 } }),
      0
    );
    expect(result.hand_position).toBe("fidgeting");
  });
});

describe("GestureAnalyzer frequency + assessment", () => {
  let analyzer: GestureAnalyzer;

  beforeEach(() => {
    analyzer = new GestureAnalyzer();
  });

  it("crossed_arms is always assessed as defensive regardless of frequency", () => {
    const result = analyzer.processFrame(
      buildPose({ leftWrist: { x: 1, y: 0 }, rightWrist: { x: -1, y: 0 } }),
      0
    );
    expect(result.assessment).toBe("defensive");
  });

  it("staying perfectly still is assessed as too_still", () => {
    let result;
    for (let t = 0; t <= 5000; t += 500) {
      result = analyzer.processFrame(buildPose(), t);
    }
    expect(result!.assessment).toBe("too_still");
  });

  it("frequent position changes are assessed as excessive", () => {
    let result;
    for (let t = 0, i = 0; t <= 2000; t += 100, i++) {
      const pose =
        i % 2 === 0
          ? buildPose()
          : buildPose({ leftWrist: { x: -2, y: -1 } }); // toggles resting <-> gesturing rapidly
      result = analyzer.processFrame(pose, t);
    }
    expect(result!.assessment).toBe("excessive");
  });

  it("a moderate, natural rate of change is assessed as natural", () => {
    let result;
    const changeTimes = [1000, 15_000, 30_000, 45_000]; // a few changes over a minute
    let i = 0;
    for (let t = 0; t <= 50_000; t += 1000) {
      const shouldToggle = changeTimes.includes(t);
      if (shouldToggle) i++;
      const pose = i % 2 === 0 ? buildPose() : buildPose({ leftWrist: { x: -2, y: -1 } });
      result = analyzer.processFrame(pose, t);
    }
    expect(result!.assessment).toBe("natural");
  });

  it("reset() clears frequency history", () => {
    for (let t = 0, i = 0; t <= 2000; t += 100, i++) {
      const pose = i % 2 === 0 ? buildPose() : buildPose({ leftWrist: { x: -2, y: -1 } });
      analyzer.processFrame(pose, t);
    }
    analyzer.reset();

    const result = analyzer.processFrame(buildPose(), 3000);
    expect(result.gesture_frequency).toBe(0);
  });
});
