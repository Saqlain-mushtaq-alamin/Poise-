/**
 * Wraps `getUserMedia` + an `AudioWorkletNode` to capture the microphone,
 * per the Phase 3 spec's §3.1. The heavy lifting (RMS/ZCR computation on
 * every audio-thread quantum) happens in the worklet processor itself —
 * see `public/worklets/mic-processor.js` — since that's real-time audio
 * work that can't run on the main thread without glitching.
 *
 * What lives here on the main thread is translation: worklet postMessage
 * events become `audio-chunk` / `speech-start` / `speech-end` /
 * `volume-level` CustomEvents, and — critically — the speech-start/
 * speech-end edge detection (only fire once per transition, not once per
 * frame) is pure logic that's fully unit-tested with a mocked worklet port
 * in MicCapture.test.ts, even though the worklet itself can't run outside
 * a real browser's audio thread.
 */

export interface MicCaptureOptions {
  deviceId?: string;
  sampleRate?: number;
}

type WorkletMessage =
  | { type: "audio-chunk"; samples: Float32Array }
  | { type: "volume-level"; level: number }
  | { type: "vad-frame"; isSpeech: boolean; timestampMs: number };

const DEFAULT_SAMPLE_RATE = 16_000;
const WORKLET_MODULE_URL = "/worklets/mic-processor.js";
const WORKLET_PROCESSOR_NAME = "mic-processor";

export class MicCapture extends EventTarget {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private wasSpeaking = false;

  get isCapturing(): boolean {
    return this.stream !== null;
  }

  async start(options: MicCaptureOptions = {}): Promise<void> {
    if (this.isCapturing) return;

    const sampleRate = options.sampleRate ?? DEFAULT_SAMPLE_RATE;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: options.deviceId ? { exact: options.deviceId } : undefined,
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: options.deviceId ? { exact: options.deviceId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    }

    const AudioCtxClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.audioContext = new AudioCtxClass({ sampleRate });
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume().catch(() => {});
    }
    await this.audioContext.audioWorklet.addModule(WORKLET_MODULE_URL);

    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(this.audioContext, WORKLET_PROCESSOR_NAME);
    this.workletNode.port.onmessage = (event: MessageEvent<WorkletMessage>) => {
      this.handleWorkletMessage(event.data);
    };

    this.sourceNode.connect(this.workletNode);
  }

  private handleWorkletMessage(data: WorkletMessage): void {
    switch (data.type) {
      case "audio-chunk":
        this.dispatchEvent(new CustomEvent<Float32Array>("audio-chunk", { detail: data.samples }));
        break;

      case "volume-level":
        this.dispatchEvent(new CustomEvent<number>("volume-level", { detail: data.level }));
        break;

      case "vad-frame":
        this.dispatchEvent(
          new CustomEvent<{ isSpeech: boolean; timestampMs: number }>("vad-frame", {
            detail: { isSpeech: data.isSpeech, timestampMs: data.timestampMs },
          })
        );

        if (data.isSpeech && !this.wasSpeaking) {
          this.wasSpeaking = true;
          this.dispatchEvent(
            new CustomEvent<{ timestampMs: number }>("speech-start", {
              detail: { timestampMs: data.timestampMs },
            })
          );
        } else if (!data.isSpeech && this.wasSpeaking) {
          this.wasSpeaking = false;
          this.dispatchEvent(
            new CustomEvent<{ timestampMs: number }>("speech-end", {
              detail: { timestampMs: data.timestampMs },
            })
          );
        }
        break;
    }
  }

  stop(): void {
    this.workletNode?.port.close();
    this.workletNode?.disconnect();
    this.sourceNode?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.audioContext?.close();

    this.workletNode = null;
    this.sourceNode = null;
    this.stream = null;
    this.audioContext = null;
    this.wasSpeaking = false;
  }
}
