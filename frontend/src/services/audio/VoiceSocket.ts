/**
 * Thin wrapper over the native WebSocket for talking to
 * `/voice/vad/status` and `/voice/stt/stream`. Exists mainly so the rest
 * of the app deals with typed callbacks instead of raw `MessageEvent`
 * parsing, and so tests can inject a fake WebSocket implementation instead
 * of needing a real server.
 */

export type VoiceSocketState = "connecting" | "open" | "closed";

export interface VoiceSocketOptions {
  onMessage: (data: unknown) => void;
  onClose?: () => void;
  onError?: (event: Event) => void;
  /** Injectable for tests; defaults to the global WebSocket constructor. */
  WebSocketImpl?: typeof WebSocket;
}

export class VoiceSocket {
  private socket: WebSocket;
  private _state: VoiceSocketState = "connecting";

  constructor(url: string, options: VoiceSocketOptions) {
    const Impl = options.WebSocketImpl ?? WebSocket;
    this.socket = new Impl(url);
    this.socket.binaryType = "arraybuffer";

    this.socket.onopen = () => {
      this._state = "open";
    };
    this.socket.onmessage = (event: MessageEvent) => {
      try {
        options.onMessage(JSON.parse(event.data));
      } catch {
        options.onMessage(event.data);
      }
    };
    this.socket.onclose = () => {
      this._state = "closed";
      options.onClose?.();
    };
    this.socket.onerror = (event: Event) => {
      options.onError?.(event);
    };
  }

  get state(): VoiceSocketState {
    return this._state;
  }

  sendBytes(data: ArrayBuffer): void {
    if (this._state !== "open") return;
    this.socket.send(data);
  }

  close(): void {
    if (this._state === "closed") return;
    this.socket.close();
  }
}

export function buildVoiceSocketUrl(port: number, path: string): string {
  return `ws://127.0.0.1:${port}${path}`;
}
