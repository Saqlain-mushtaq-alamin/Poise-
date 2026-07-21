import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useConfidenceTracking } from "./useConfidenceTracking";

const fakeTrack = { stop: vi.fn() };
const fakeStream = { getTracks: () => [fakeTrack] };
const getUserMedia = vi.fn();
let fakeVideo: { srcObject: unknown; muted: boolean; play: ReturnType<typeof vi.fn> };
let fakeCanvas: { width: number; height: number; getContext: ReturnType<typeof vi.fn> };
let originalCreateElement: typeof document.createElement;

beforeEach(() => {
  fakeTrack.stop.mockClear();
  getUserMedia.mockReset().mockResolvedValue(fakeStream);

  fakeVideo = { srcObject: null, muted: false, play: vi.fn().mockResolvedValue(undefined) };
  fakeCanvas = {
    width: 0,
    height: 0,
    getContext: vi.fn().mockReturnValue({
      drawImage: vi.fn(),
      getImageData: vi.fn().mockReturnValue({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
    }),
  };

  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal("requestAnimationFrame", vi.fn().mockReturnValue(1));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  originalCreateElement = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
    if (tag === "video") return fakeVideo as unknown as HTMLVideoElement;
    if (tag === "canvas") return fakeCanvas as unknown as HTMLCanvasElement;
    return originalCreateElement(tag);
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useConfidenceTracking", () => {
  it("is not tracking initially", () => {
    const { result } = renderHook(() =>
      useConfidenceTracking({ api: null, sessionId: null, coachingEnabled: true })
    );
    expect(result.current.isTracking).toBe(false);
  });

  it("start() requests the webcam and sets isTracking true", async () => {
    const { result } = renderHook(() =>
      useConfidenceTracking({ api: null, sessionId: null, coachingEnabled: true })
    );

    await act(async () => {
      await result.current.start();
    });

    expect(getUserMedia).toHaveBeenCalled();
    await waitFor(() => expect(result.current.isTracking).toBe(true));
  });

  it("surfaces an error when the webcam fails to start", async () => {
    getUserMedia.mockRejectedValue(new Error("Permission denied"));
    const { result } = renderHook(() =>
      useConfidenceTracking({ api: null, sessionId: null, coachingEnabled: true })
    );

    await act(async () => {
      await result.current.start();
    });

    await waitFor(() => expect(result.current.error).toBe("Permission denied"));
    expect(result.current.isTracking).toBe(false);
  });

  it("stop() releases the webcam and resets tracking state", async () => {
    const { result } = renderHook(() =>
      useConfidenceTracking({ api: null, sessionId: null, coachingEnabled: true })
    );

    await act(async () => {
      await result.current.start();
    });
    await waitFor(() => expect(result.current.isTracking).toBe(true));

    act(() => {
      result.current.stop();
    });

    expect(fakeTrack.stop).toHaveBeenCalled();
    expect(result.current.isTracking).toBe(false);
    expect(result.current.latestResult).toBeNull();
  });

  it("dismissTip() clears the current coaching tip", () => {
    const { result } = renderHook(() =>
      useConfidenceTracking({ api: null, sessionId: null, coachingEnabled: true })
    );

    act(() => {
      result.current.dismissTip();
    });
    expect(result.current.coachingTip).toBeNull();
  });
});
