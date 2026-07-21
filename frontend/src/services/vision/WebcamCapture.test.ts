import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WebcamCapture } from "./WebcamCapture";

const fakeTrack = { stop: vi.fn() };
const fakeStream = { getTracks: () => [fakeTrack] };
const getUserMedia = vi.fn().mockResolvedValue(fakeStream);
const enumerateDevices = vi.fn().mockResolvedValue([
  { deviceId: "cam-1", kind: "videoinput", label: "Front Camera" },
  { deviceId: "mic-1", kind: "audioinput", label: "Built-in Mic" },
]);

let fakeVideo: {
  srcObject: unknown;
  muted: boolean;
  play: ReturnType<typeof vi.fn>;
};
let fakeCanvasCtx: { drawImage: ReturnType<typeof vi.fn>; getImageData: ReturnType<typeof vi.fn> };
let fakeCanvas: { width: number; height: number; getContext: ReturnType<typeof vi.fn> };

let originalCreateElement: typeof document.createElement;

beforeEach(() => {
  fakeTrack.stop.mockClear();
  getUserMedia.mockReset().mockResolvedValue(fakeStream);
  enumerateDevices.mockReset().mockResolvedValue([
    { deviceId: "cam-1", kind: "videoinput", label: "Front Camera" },
    { deviceId: "mic-1", kind: "audioinput", label: "Built-in Mic" },
  ]);

  fakeVideo = { srcObject: null, muted: false, play: vi.fn().mockResolvedValue(undefined) };
  fakeCanvasCtx = {
    drawImage: vi.fn(),
    getImageData: vi.fn().mockReturnValue({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
  };
  fakeCanvas = { width: 0, height: 0, getContext: vi.fn().mockReturnValue(fakeCanvasCtx) };

  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia, enumerateDevices } });

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

describe("WebcamCapture", () => {
  it("is not capturing before start()", () => {
    const webcam = new WebcamCapture();
    expect(webcam.isCapturing).toBe(false);
  });

  it("requests the camera with 640x480@30fps by default", async () => {
    const webcam = new WebcamCapture();
    await webcam.start();

    expect(getUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({
        video: expect.objectContaining({ width: 640, height: 480, frameRate: 30 }),
      })
    );
    expect(webcam.isCapturing).toBe(true);
  });

  it("passes an exact deviceId constraint when one is given", async () => {
    const webcam = new WebcamCapture();
    await webcam.start({ deviceId: "cam-42" });

    expect(getUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({
        video: expect.objectContaining({ deviceId: { exact: "cam-42" } }),
      })
    );
  });

  it("does nothing if start() is called while already capturing", async () => {
    const webcam = new WebcamCapture();
    await webcam.start();
    await webcam.start();
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("getFrame() returns null before capture starts", () => {
    const webcam = new WebcamCapture();
    expect(webcam.getFrame()).toBeNull();
  });

  it("getFrame() draws the video frame and returns ImageData once capturing", async () => {
    const webcam = new WebcamCapture();
    await webcam.start();

    const frame = webcam.getFrame();
    expect(fakeCanvasCtx.drawImage).toHaveBeenCalled();
    expect(fakeCanvasCtx.getImageData).toHaveBeenCalled();
    expect(frame).not.toBeNull();
  });

  it("listDevices() returns only video input devices", async () => {
    const webcam = new WebcamCapture();
    const devices = await webcam.listDevices();
    expect(devices).toHaveLength(1);
    expect(devices[0].deviceId).toBe("cam-1");
  });

  it("stop() releases tracks and clears state", async () => {
    const webcam = new WebcamCapture();
    await webcam.start();
    webcam.stop();

    expect(fakeTrack.stop).toHaveBeenCalledTimes(1);
    expect(webcam.isCapturing).toBe(false);
    expect(webcam.getFrame()).toBeNull();
  });

  it("stop() is safe to call before start()", () => {
    const webcam = new WebcamCapture();
    expect(() => webcam.stop()).not.toThrow();
  });
});
