import { describe, expect, it } from "vitest";

import { computeCompositeScore } from "./confidenceScorer";

const STRONG = {
  eyeContactRatio: 1.0,
  stabilityScore: 1.0,
  blinkAssessment: "normal" as const,
  expression: "happy" as const,
  gestureAssessment: "natural" as const,
  gazeDirection: "direct" as const,
};

const WEAK = {
  eyeContactRatio: 0.1,
  stabilityScore: 0.2,
  blinkAssessment: "elevated" as const,
  expression: "anxious" as const,
  gestureAssessment: "defensive" as const,
  gazeDirection: "away_left" as const,
};

describe("computeCompositeScore", () => {
  it("scores a strong signal set near 100", () => {
    expect(computeCompositeScore(STRONG)).toBeGreaterThanOrEqual(95);
  });

  it("scores a weak signal set low", () => {
    expect(computeCompositeScore(WEAK)).toBeLessThanOrEqual(35);
  });

  it("always returns a value between 0 and 100", () => {
    const score = computeCompositeScore(WEAK);
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(100);
  });

  it("higher eye contact ratio increases the score, all else equal", () => {
    const low = computeCompositeScore({ ...STRONG, eyeContactRatio: 0.2 });
    const high = computeCompositeScore({ ...STRONG, eyeContactRatio: 1.0 });
    expect(high).toBeGreaterThan(low);
  });

  it("works without a gesture assessment (redistributes its weight)", () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { gestureAssessment: _gestureAssessment, ...withoutGesture } = STRONG;
    const score = computeCompositeScore(withoutGesture);
    expect(score).toBeGreaterThanOrEqual(95);
  });

  it("normal blink rate scores higher than elevated blink rate, all else equal", () => {
    const normal = computeCompositeScore({ ...STRONG, blinkAssessment: "normal" });
    const elevated = computeCompositeScore({ ...STRONG, blinkAssessment: "elevated" });
    expect(normal).toBeGreaterThan(elevated);
  });

  it("happy expression scores higher than anxious, all else equal", () => {
    const happy = computeCompositeScore({ ...STRONG, expression: "happy" });
    const anxious = computeCompositeScore({ ...STRONG, expression: "anxious" });
    expect(happy).toBeGreaterThan(anxious);
  });
});
