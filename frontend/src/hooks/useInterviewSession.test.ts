import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PoiseAPI } from "../lib/api";
import { useInterviewSession } from "./useInterviewSession";

function fakeApi(overrides: Partial<PoiseAPI> = {}): PoiseAPI {
  return {
    createInterviewSession: vi.fn().mockResolvedValue({
      session_id: "s1",
      state: "ready",
      persona_id: "professional",
      session_mode: "practice",
      plan: { sections: [], estimated_duration_minutes: 20, coverage_matrix: {} },
    }),
    startInterviewSession: vi.fn().mockResolvedValue({ message: "Hi there!", is_complete: false }),
    respondToWarmUp: vi.fn(),
    submitAnswer: vi.fn(),
    endInterviewSession: vi.fn().mockResolvedValue({
      session_id: "s1",
      state: "completed",
      persona_id: "professional",
      session_mode: "practice",
      plan: null,
    }),
    getInterviewEvaluations: vi.fn().mockResolvedValue([]),
    ...overrides,
  } as unknown as PoiseAPI;
}

describe("useInterviewSession", () => {
  it("createAndStart drives the machine to inProgress.asking and shows the greeting", async () => {
    const api = fakeApi();
    const { result } = renderHook(() => useInterviewSession(api));

    await act(async () => {
      await result.current.createAndStart("r1", "j1", {}, "professional");
    });

    expect(result.current.sessionId).toBe("s1");
    expect(result.current.currentMessage).toBe("Hi there!");
    expect(result.current.machineState).toBe("warmUp");
  });

  it("respondToWarmUp advances to the first question once warm-up completes", async () => {
    const api = fakeApi({
      respondToWarmUp: vi.fn().mockResolvedValue({
        message: "Great, let's begin.",
        is_complete: true,
        first_question: "Tell me about yourself.",
        question_id: "q1",
      }),
    });
    const { result } = renderHook(() => useInterviewSession(api));

    await act(async () => {
      await result.current.createAndStart("r1", "j1", {}, "professional");
    });
    await act(async () => {
      await result.current.respondToWarmUp("ready!");
    });

    expect(result.current.machineState).toEqual(JSON.stringify({ inProgress: "listening" }));
    expect(result.current.currentMessage).toBe("Tell me about yourself.");
  });

  it("submitAnswer with next_question advances the machine and updates the message", async () => {
    const api = fakeApi({
      respondToWarmUp: vi.fn().mockResolvedValue({
        message: "Let's begin.",
        is_complete: true,
        first_question: "Q1?",
        question_id: "q1",
      }),
      submitAnswer: vi.fn().mockResolvedValue({
        score: 0.9,
        feedback: "Great",
        reaction: "Nice!",
        next_action: "next_question",
        next_message: "Q2?",
        next_question_id: "q2",
        framework_missing: [],
      }),
    });
    const { result } = renderHook(() => useInterviewSession(api));

    await act(async () => {
      await result.current.createAndStart("r1", "j1", {}, "professional");
    });
    await act(async () => {
      await result.current.respondToWarmUp("ready!");
    });
    await act(async () => {
      await result.current.submitAnswer("My answer");
    });

    expect(result.current.lastFeedback?.score).toBe(0.9);
    expect(result.current.currentMessage).toBe("Q2?");
    expect(result.current.machineState).toEqual(JSON.stringify({ inProgress: "listening" }));
  });

  it("submitAnswer with session_complete marks the session as complete", async () => {
    const api = fakeApi({
      respondToWarmUp: vi.fn().mockResolvedValue({
        message: "Let's begin.",
        is_complete: true,
        first_question: "Q1?",
        question_id: "q1",
      }),
      submitAnswer: vi.fn().mockResolvedValue({
        score: 0.9,
        feedback: "Great",
        reaction: null,
        next_action: "session_complete",
        framework_missing: [],
      }),
    });
    const { result } = renderHook(() => useInterviewSession(api));

    await act(async () => {
      await result.current.createAndStart("r1", "j1", {}, "professional");
    });
    await act(async () => {
      await result.current.respondToWarmUp("ready!");
    });
    await act(async () => {
      await result.current.submitAnswer("My final answer");
    });

    expect(result.current.isComplete).toBe(true);
  });

  it("surfaces an error message when the API call fails", async () => {
    const api = fakeApi({
      createInterviewSession: vi.fn().mockRejectedValue(new Error("network down")),
    });
    const { result } = renderHook(() => useInterviewSession(api));

    await act(async () => {
      await result.current.createAndStart("r1", "j1", {}, "professional");
    });

    await waitFor(() => expect(result.current.error).toBe("network down"));
  });

  it("does nothing and sets an error when api is null", async () => {
    const { result } = renderHook(() => useInterviewSession(null));

    await act(async () => {
      await result.current.createAndStart("r1", "j1", {}, "professional");
    });

    expect(result.current.error).toBe("Sidecar not connected yet");
    expect(result.current.sessionId).toBeNull();
  });
});
