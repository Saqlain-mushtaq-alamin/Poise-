import { describe, expect, it } from "vitest";
import { cleanSpeechText, getSharedAudioContext, unlockGlobalAudio } from "./audio-manager";

describe("audio-manager", () => {
  it("cleans markdown formatting for natural human speech", () => {
    const raw = "**Question 1:** What is the difference between `let` and `const`? # Important\n\n- Point 1\n- Point 2";
    const cleaned = cleanSpeechText(raw);

    expect(cleaned).not.toContain("**");
    expect(cleaned).not.toContain("`");
    expect(cleaned).not.toContain("#");
    expect(cleaned).toContain("Question 1: What is the difference between let and const?");
  });

  it("handles empty or whitespace strings gracefully", () => {
    expect(cleanSpeechText("")).toBe("");
    expect(cleanSpeechText("   ")).toBe("");
  });

  it("getSharedAudioContext returns a valid context or object", () => {
    const ctx = getSharedAudioContext();
    expect(ctx).toBeDefined();
  });

  it("unlockGlobalAudio executes without throwing", () => {
    expect(() => unlockGlobalAudio()).not.toThrow();
  });
});
