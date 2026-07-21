import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MicCapture } from "./MicCapture";

let lastWorkletNode: FakeAudioWorkletNode | null = null;
let lastAudioContext: FakeAudioContext | null = null;

class FakeAudioContext {
  audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
  createMediaStreamSource = vi.fn().mockReturnValue({ connect: vi.fn(), disconnect: vi.fn() });
  close = vi.fn().mockResolvedValue(undefined);

  constructor(public options: { sampleRate: number }) {
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- capturing the instance for test assertions
    lastAudioContext = this;
  }
}

class FakeAudioWorkletNode {
  port: { onmessage: ((event: { data: unknown }) => void) | null; close: () => void } = {
    onmessage: null,
    close: vi.fn(),
  };
  disconnect = vi.fn();

  constructor(
    public context: FakeAudioContext,
    public name: string
  ) {
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- capturing the instance for test assertions
    lastWorkletNode = this;
  }

  emit(data: unknown) {
    this.port.onmessage?.({ data });
  }
}

const fakeTrack = { stop: vi.fn() };
const fakeStream = { getTracks: () => [fakeTrack] };
const getUserMedia = vi.fn().mockResolvedValue(fakeStream);

beforeEach(() => {
  lastWorkletNode = null;
  lastAudioContext = null;
  fakeTrack.stop.mockClear();
  getUserMedia.mockClear();

  vi.stubGlobal("AudioContext", FakeAudioContext);
  vi.stubGlobal("AudioWorkletNode", FakeAudioWorkletNode);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MicCapture", () => {
  it("is not capturing before start()", () => {
    const mic = new MicCapture();
    expect(mic.isCapturing).toBe(false);
  });

  it("requests the microphone with 16kHz mono constraints by default", async () => {
    const mic = new MicCapture();
    await mic.start();

    expect(getUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({
        audio: expect.objectContaining({ sampleRate: 16000, channelCount: 1 }),
      })
    );
    expect(mic.isCapturing).toBe(true);
  });

  it("passes an exact deviceId constraint when one is given", async () => {
    const mic = new MicCapture();
    await mic.start({ deviceId: "device-42" });

    expect(getUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({
        audio: expect.objectContaining({ deviceId: { exact: "device-42" } }),
      })
    );
  });

  it("loads the worklet module and connects the source to it", async () => {
    const mic = new MicCapture();
    await mic.start();

    expect(lastAudioContext?.audioWorklet.addModule).toHaveBeenCalledWith(
      "/worklets/mic-processor.js"
    );
    expect(lastAudioContext?.createMediaStreamSource).toHaveBeenCalledWith(fakeStream);
  });

  it("does nothing if start() is called while already capturing", async () => {
    const mic = new MicCapture();
    await mic.start();
    await mic.start();

    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("re-emits worklet audio-chunk messages as a CustomEvent", async () => {
    const mic = new MicCapture();
    await mic.start();

    const handler = vi.fn();
    mic.addEventListener("audio-chunk", handler);

    const samples = new Float32Array([0.1, 0.2, 0.3]);
    lastWorkletNode!.emit({ type: "audio-chunk", samples });

    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent<Float32Array>;
    expect(event.detail).toBe(samples);
  });

  it("re-emits worklet volume-level messages as a CustomEvent", async () => {
    const mic = new MicCapture();
    await mic.start();

    const handler = vi.fn();
    mic.addEventListener("volume-level", handler);
    lastWorkletNode!.emit({ type: "volume-level", level: 0.42 });

    expect(handler).toHaveBeenCalledTimes(1);
    expect((handler.mock.calls[0][0] as CustomEvent<number>).detail).toBe(0.42);
  });

  it("fires speech-start only on the silence-to-speech transition, not every frame", async () => {
    const mic = new MicCapture();
    await mic.start();

    const startHandler = vi.fn();
    mic.addEventListener("speech-start", startHandler);

    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 0 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 30 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 60 });

    expect(startHandler).toHaveBeenCalledTimes(1);
  });

  it("fires speech-end only on the speech-to-silence transition", async () => {
    const mic = new MicCapture();
    await mic.start();

    const endHandler = vi.fn();
    mic.addEventListener("speech-end", endHandler);

    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 0 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: false, timestampMs: 30 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: false, timestampMs: 60 });

    expect(endHandler).toHaveBeenCalledTimes(1);
  });

  it("fires speech-start again after a full speech-end cycle", async () => {
    const mic = new MicCapture();
    await mic.start();

    const startHandler = vi.fn();
    mic.addEventListener("speech-start", startHandler);

    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 0 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: false, timestampMs: 30 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 60 });

    expect(startHandler).toHaveBeenCalledTimes(2);
  });

  it("re-emits every raw vad-frame, not just transitions (for barge-in debounce logic)", async () => {
    const mic = new MicCapture();
    await mic.start();

    const frameHandler = vi.fn();
    mic.addEventListener("vad-frame", frameHandler);

    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 0 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 30 });
    lastWorkletNode!.emit({ type: "vad-frame", isSpeech: true, timestampMs: 60 });

    expect(frameHandler).toHaveBeenCalledTimes(3);
    expect((frameHandler.mock.calls[2][0] as CustomEvent).detail).toEqual({
      isSpeech: true,
      timestampMs: 60,
    });
  });

  it("stop() releases the mic tracks and closes the audio context", async () => {
    const mic = new MicCapture();
    await mic.start();
    mic.stop();

    expect(fakeTrack.stop).toHaveBeenCalledTimes(1);
    expect(lastAudioContext?.close).toHaveBeenCalledTimes(1);
    expect(mic.isCapturing).toBe(false);
  });

  it("stop() is safe to call before start()", () => {
    const mic = new MicCapture();
    expect(() => mic.stop()).not.toThrow();
  });
});
