import { renderHook, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useVoiceInterview } from "./useVoiceInterview";

describe("useVoiceInterview", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete (window as unknown as Record<string, unknown>).__TAURI__;
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
    delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
    delete (window as unknown as Record<string, unknown>).SpeechRecognition;
  });

  it("initializes in idle phase with empty transcript", () => {
    const { result } = renderHook(() =>
      useVoiceInterview({
        backendBaseUrl: "http://127.0.0.1:8000",
        onAnswerReady: vi.fn(),
      })
    );

    expect(result.current.phase).toBe("idle");
    expect(result.current.transcript).toBe("");
    expect(result.current.interimTranscript).toBe("");
  });

  it("marks speechApiAvailable as false when running in Tauri environment even if webkitSpeechRecognition exists", () => {
    // In Windows WebView2, webkitSpeechRecognition is defined on window, but lacks Google credentials
    (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
    (window as unknown as Record<string, unknown>).webkitSpeechRecognition = class MockSR {};

    const { result } = renderHook(() =>
      useVoiceInterview({
        backendBaseUrl: "http://127.0.0.1:8000",
        onAnswerReady: vi.fn(),
      })
    );

    expect(result.current.speechApiAvailable).toBe(false);
  });

  it("marks speechApiAvailable as true when running in regular browser with SpeechRecognition", () => {
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
    delete (window as unknown as Record<string, unknown>).__TAURI__;
    (window as unknown as Record<string, unknown>).webkitSpeechRecognition = class MockSR {};

    const { result } = renderHook(() =>
      useVoiceInterview({
        backendBaseUrl: "http://127.0.0.1:8000",
        onAnswerReady: vi.fn(),
      })
    );

    expect(result.current.speechApiAvailable).toBe(true);
  });

  it("clearTranscript resets transcript state", () => {
    const { result } = renderHook(() =>
      useVoiceInterview({
        backendBaseUrl: "http://127.0.0.1:8000",
        onAnswerReady: vi.fn(),
      })
    );

    act(() => {
      result.current.clearTranscript();
    });

    expect(result.current.transcript).toBe("");
    expect(result.current.interimTranscript).toBe("");
  });

  it("accepts custom timers in startListening", async () => {
    const onAnswerReady = vi.fn();
    const { result } = renderHook(() =>
      useVoiceInterview({
        backendBaseUrl: "http://127.0.0.1:8000",
        onAnswerReady,
      })
    );

    expect(typeof result.current.startListening).toBe("function");
    // Verify startListening is callable with dynamic timer options without throwing
    await act(async () => {
      Object.defineProperty(navigator, "mediaDevices", {
        value: {
          getUserMedia: vi.fn().mockRejectedValue(new Error("No test mic")),
        },
        configurable: true,
        writable: true,
      });
      await result.current.startListening({ maxListenSecs: 130, silenceThresholdSecs: 5.5 });
    });
    // Expected graceful mic error without uncaught promise rejection
    expect(result.current.micError).toContain("Microphone error");
  });
});

