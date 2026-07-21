import { beforeEach, describe, expect, it, vi } from "vitest";

import { TTSPlayback } from "./TTSPlayback";

interface FakeSourceNode {
  buffer: unknown;
  onended: (() => void) | null;
  connect: ReturnType<typeof vi.fn>;
  start: ReturnType<typeof vi.fn>;
  stop: ReturnType<typeof vi.fn>;
}

let createdSources: FakeSourceNode[] = [];

class FakeAudioContext {
  currentTime = 0;
  destination = {};

  decodeAudioData = vi.fn().mockImplementation(async () => ({ duration: 0.5 }));

  createBufferSource = vi.fn().mockImplementation((): FakeSourceNode => {
    const node: FakeSourceNode = {
      buffer: null,
      onended: null,
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(() => {
        node.onended?.();
      }),
    };
    createdSources.push(node);
    return node;
  });
}

function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  let i = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(chunks[i++]);
      } else {
        controller.close();
      }
    },
  });
}

function chunk(byte: number, length = 4): Uint8Array {
  return new Uint8Array(length).fill(byte);
}

beforeEach(() => {
  createdSources = [];
});

describe("TTSPlayback", () => {
  it("is not playing before any stream starts", () => {
    const playback = new TTSPlayback(new FakeAudioContext() as unknown as AudioContext);
    expect(playback.isPlaying).toBe(false);
  });

  it("schedules one buffer source per chunk and connects it to the destination", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);

    await playback.playStream(streamOf([chunk(1), chunk(2)]));

    expect(createdSources).toHaveLength(2);
    expect(createdSources[0].connect).toHaveBeenCalledWith(ctx.destination);
    expect(createdSources[0].start).toHaveBeenCalled();
    expect(createdSources[1].start).toHaveBeenCalled();
  });

  it("skips empty chunks without creating a source for them", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);

    await playback.playStream(streamOf([chunk(1), new Uint8Array(0), chunk(2)]));

    expect(createdSources).toHaveLength(2);
  });

  it("fires playback-started once, on the first scheduled chunk", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);
    const handler = vi.fn();
    playback.addEventListener("playback-started", handler);

    await playback.playStream(streamOf([chunk(1), chunk(2), chunk(3)]));

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("reports isPlaying true while chunks are scheduled and not yet ended", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);

    await playback.playStream(streamOf([chunk(1)]));

    expect(playback.isPlaying).toBe(true);
  });

  it("fires playback-ended once every scheduled source has ended", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);
    const endedHandler = vi.fn();
    playback.addEventListener("playback-ended", endedHandler);

    await playback.playStream(streamOf([chunk(1), chunk(2)]));
    expect(endedHandler).not.toHaveBeenCalled();

    createdSources[0].onended?.();
    expect(endedHandler).not.toHaveBeenCalled(); // one source still pending

    createdSources[1].onended?.();
    expect(endedHandler).toHaveBeenCalledTimes(1);
    expect(playback.isPlaying).toBe(false);
  });

  it("stop() halts every scheduled source and fires playback-interrupted", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);
    const interruptedHandler = vi.fn();
    playback.addEventListener("playback-interrupted", interruptedHandler);

    await playback.playStream(streamOf([chunk(1), chunk(2)]));
    playback.stop();

    expect(createdSources[0].stop).toHaveBeenCalled();
    expect(createdSources[1].stop).toHaveBeenCalled();
    expect(interruptedHandler).toHaveBeenCalledTimes(1);
    expect(playback.isPlaying).toBe(false);
  });

  it("stop() is a no-op (no event) when nothing was playing", () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);
    const interruptedHandler = vi.fn();
    playback.addEventListener("playback-interrupted", interruptedHandler);

    playback.stop();

    expect(interruptedHandler).not.toHaveBeenCalled();
  });

  it("a stopped source's onended does not double-fire playback-ended", async () => {
    const ctx = new FakeAudioContext();
    const playback = new TTSPlayback(ctx as unknown as AudioContext);
    const endedHandler = vi.fn();
    playback.addEventListener("playback-ended", endedHandler);

    await playback.playStream(streamOf([chunk(1)]));
    playback.stop(); // clears onended before calling stop() on the node

    expect(endedHandler).not.toHaveBeenCalled();
  });
});
