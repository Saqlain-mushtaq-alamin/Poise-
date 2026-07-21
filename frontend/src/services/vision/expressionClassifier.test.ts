import { describe, expect, it } from "vitest";

import { classifyExpression } from "./expressionClassifier";
import { FACE, type Point3D } from "./landmarks";

interface FacePoints {
  mouthLeft?: { x: number; y: number };
  mouthRight?: { x: number; y: number };
  mouthTop?: { x: number; y: number };
  mouthBottom?: { x: number; y: number };
  leftBrow?: { x: number; y: number };
  rightBrow?: { x: number; y: number };
}

function buildLandmarks(points: FacePoints = {}): Point3D[] {
  const landmarks: Point3D[] = new Array(478).fill(null).map(() => ({ x: 0, y: 0, z: 0 }));
  landmarks[FACE.LEFT_EYE_OUTER] = { x: -1, y: 0, z: 0 };
  landmarks[FACE.RIGHT_EYE_OUTER] = { x: 1, y: 0, z: 0 };
  landmarks[FACE.FOREHEAD] = { x: 0, y: -1, z: 0 };
  landmarks[FACE.CHIN] = { x: 0, y: 1, z: 0 };
  landmarks[FACE.LEFT_MOUTH_CORNER] = { x: -0.3, y: 0.5, z: 0, ...points.mouthLeft };
  landmarks[FACE.RIGHT_MOUTH_CORNER] = { x: 0.3, y: 0.5, z: 0, ...points.mouthRight };
  landmarks[FACE.UPPER_LIP_TOP] = { x: 0, y: 0.45, z: 0, ...points.mouthTop };
  landmarks[FACE.LOWER_LIP_BOTTOM] = { x: 0, y: 0.55, z: 0, ...points.mouthBottom };
  landmarks[FACE.LEFT_EYEBROW_INNER] = { x: -1, y: 0, z: 0, ...points.leftBrow };
  landmarks[FACE.RIGHT_EYEBROW_INNER] = { x: 1, y: 0, z: 0, ...points.rightBrow };
  return landmarks;
}

const NEUTRAL_INPUTS = { avgEar: 0.3, blinksPerMinute: 15 };

describe("classifyExpression", () => {
  it("classifies a baseline face as neutral", () => {
    const result = classifyExpression(buildLandmarks(), NEUTRAL_INPUTS);
    expect(result.expression).toBe("neutral");
  });

  it("classifies a wide mouth (smile) as happy", () => {
    const result = classifyExpression(
      buildLandmarks({ mouthLeft: { x: -0.5, y: 0.5 }, mouthRight: { x: 0.5, y: 0.5 } }),
      NEUTRAL_INPUTS
    );
    expect(result.expression).toBe("happy");
  });

  it("classifies an open mouth + raised eyebrows as surprised", () => {
    const result = classifyExpression(
      buildLandmarks({
        mouthTop: { x: 0, y: 0.1 },
        mouthBottom: { x: 0, y: 0.9 },
        leftBrow: { x: -1, y: -0.1 },
        rightBrow: { x: 1, y: -0.1 },
      }),
      NEUTRAL_INPUTS
    );
    expect(result.expression).toBe("surprised");
  });

  it("classifies asymmetric eyebrows as confused", () => {
    const result = classifyExpression(
      buildLandmarks({ leftBrow: { x: -1, y: -0.1 }, rightBrow: { x: 1, y: 0 } }),
      NEUTRAL_INPUTS
    );
    expect(result.expression).toBe("confused");
  });

  it("classifies elevated blink rate + narrowed eyes as anxious", () => {
    const result = classifyExpression(buildLandmarks(), { avgEar: 0.15, blinksPerMinute: 30 });
    expect(result.expression).toBe("anxious");
  });

  it("classifies lowered eyebrows with an otherwise neutral face as focused", () => {
    const result = classifyExpression(
      buildLandmarks({ leftBrow: { x: -1, y: 0.1 }, rightBrow: { x: 1, y: 0.1 } }),
      NEUTRAL_INPUTS
    );
    expect(result.expression).toBe("focused");
  });

  it("every classification includes a confidence between 0 and 1", () => {
    const result = classifyExpression(buildLandmarks(), NEUTRAL_INPUTS);
    expect(result.confidence).toBeGreaterThanOrEqual(0);
    expect(result.confidence).toBeLessThanOrEqual(1);
  });

  it("surprise takes priority over a simultaneously wide mouth", () => {
    // Wide + open mouth with raised brows should read as surprise, not happy,
    // since surprise is checked first (more specific / stronger signal).
    const result = classifyExpression(
      buildLandmarks({
        mouthLeft: { x: -0.5, y: 0.5 },
        mouthRight: { x: 0.5, y: 0.5 },
        mouthTop: { x: 0, y: 0.1 },
        mouthBottom: { x: 0, y: 0.9 },
        leftBrow: { x: -1, y: -0.1 },
        rightBrow: { x: 1, y: -0.1 },
      }),
      NEUTRAL_INPUTS
    );
    expect(result.expression).toBe("surprised");
  });
});
