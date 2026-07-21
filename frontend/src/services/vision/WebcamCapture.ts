/**
 * Browser webcam capture, per Phase 5 spec §5.1. Structurally identical
 * to Phase 3's MicCapture — `getUserMedia` + cleanup — so it's tested the
 * same way, with jsdom-mocked `navigator.mediaDevices` and `HTMLVideoElement`.
 *
 * Frame extraction draws the current video frame to an offscreen canvas
 * and reads it back as ImageData — standard, real browser API usage that
 * works the same in test-mocked and real environments alike, unlike the
 * actual MediaPipe inference this feeds into (see FaceAnalyzer.ts).
 */

export interface WebcamCaptureOptions {
  deviceId?: string;
  width?: number;
  height?: number;
  frameRate?: number;
}

const DEFAULTS = { width: 640, height: 480, frameRate: 30 };

export class WebcamCapture {
  private stream: MediaStream | null = null;
  private videoElement: HTMLVideoElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;

  get isCapturing(): boolean {
    return this.stream !== null;
  }

  async start(options: WebcamCaptureOptions = {}): Promise<void> {
    if (this.isCapturing) return;

    const width = options.width ?? DEFAULTS.width;
    const height = options.height ?? DEFAULTS.height;
    const frameRate = options.frameRate ?? DEFAULTS.frameRate;

    this.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: options.deviceId ? { exact: options.deviceId } : undefined,
        width,
        height,
        frameRate,
      },
    });

    this.videoElement = document.createElement("video");
    this.videoElement.srcObject = this.stream;
    this.videoElement.muted = true;
    await this.videoElement.play();

    this.canvas = document.createElement("canvas");
    this.canvas.width = width;
    this.canvas.height = height;
    this.ctx = this.canvas.getContext("2d");
  }

  /** Draws the current video frame to the offscreen canvas and returns it
   * as ImageData for a face/pose analyzer to consume. Returns null if
   * capture hasn't started, rather than throwing — callers in a render
   * loop shouldn't need a try/catch around every frame. */
  getFrame(): ImageData | null {
    if (!this.videoElement || !this.canvas || !this.ctx) return null;
    this.ctx.drawImage(this.videoElement, 0, 0, this.canvas.width, this.canvas.height);
    return this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
  }

  async listDevices(): Promise<MediaDeviceInfo[]> {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
      return [];
    }
    const all = await navigator.mediaDevices.enumerateDevices();
    return all.filter((d) => d.kind === "videoinput");
  }

  stop(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }
    this.stream = null;
    this.videoElement = null;
    this.canvas = null;
    this.ctx = null;
  }
}
