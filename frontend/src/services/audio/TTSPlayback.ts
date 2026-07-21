/**
 * Plays back streamed WAV chunks from `/voice/tts/synthesize` as they
 * arrive, per the Phase 3 spec's §3.5 — decode each chunk as soon as it's
 * read from the response stream and queue it onto one continuous
 * AudioContext timeline, so playback starts after the first chunk instead
 * of waiting for the whole response.
 *
 * `stop()` is what TurnManager's `onInterruptPlayback` callback should
 * call for barge-in: it stops every scheduled/playing source immediately
 * and clears anything still queued.
 */

export type TTSPlaybackEventType = "playback-started" | "playback-ended" | "playback-interrupted";

export class TTSPlayback extends EventTarget {
  private audioContext: AudioContext;
  private scheduledSources: AudioBufferSourceNode[] = [];
  private nextStartTime = 0;
  private playing = false;
  private pendingCount = 0;

  constructor(audioContext?: AudioContext) {
    super();
    this.audioContext = audioContext ?? new AudioContext();
  }

  get isPlaying(): boolean {
    return this.playing;
  }

  get currentPosition(): number {
    if (!this.playing) return 0;
    return Math.max(0, this.audioContext.currentTime) * 1000;
  }

  /**
   * Reads a WAV byte stream chunk by chunk, decoding and scheduling each
   * one back-to-back as it arrives. Each chunk from
   * `TTSEngine.synthesize_stream` (backend) is itself a complete, valid
   * WAV file, so `decodeAudioData` can be called per-chunk rather than
   * needing to reassemble one giant buffer first.
   */
  async playStream(stream: ReadableStream<Uint8Array>): Promise<void> {
    this.nextStartTime = this.audioContext.currentTime;
    const reader = stream.getReader();

    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!value || value.byteLength === 0) continue;

        this.pendingCount++;
        try {
          await this.scheduleChunk(value);
        } finally {
          this.pendingCount--;
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  private async scheduleChunk(bytes: Uint8Array): Promise<void> {
    // Copy into a fresh ArrayBuffer — decodeAudioData detaches/consumes
    // the buffer it's given, and `bytes` may share memory the caller
    // still expects to be readable afterwards.
    const arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer as ArrayBuffer);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    const startAt = Math.max(this.nextStartTime, this.audioContext.currentTime);
    source.start(startAt);
    this.nextStartTime = startAt + audioBuffer.duration;

    this.scheduledSources.push(source);
    if (!this.playing) {
      this.playing = true;
      this.dispatchEvent(new CustomEvent("playback-started"));
    }

    source.onended = () => {
      this.scheduledSources = this.scheduledSources.filter((s) => s !== source);
      if (this.scheduledSources.length === 0 && this.pendingCount === 0 && this.playing) {
        this.playing = false;
        this.dispatchEvent(new CustomEvent("playback-ended"));
      }
    };
  }

  /** Immediately halts playback and drops anything still queued — the
   * barge-in path. Safe to call even if nothing is playing. */
  stop(): void {
    const wasPlaying = this.playing;
    for (const source of this.scheduledSources) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        // Already stopped/ended — nothing to do.
      }
    }
    this.scheduledSources = [];
    this.nextStartTime = this.audioContext.currentTime;
    this.pendingCount = 0;
    this.playing = false;

    if (wasPlaying) {
      this.dispatchEvent(new CustomEvent("playback-interrupted"));
    }
  }
}
