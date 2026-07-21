import { describe, expect, it, vi } from "vitest";

import { buildVoiceSocketUrl, VoiceSocket } from "./VoiceSocket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  binaryType = "";
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => this.onclose?.());

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
}

describe("buildVoiceSocketUrl", () => {
  it("builds a ws:// URL against the sidecar's localhost port", () => {
    expect(buildVoiceSocketUrl(54321, "/voice/vad/status")).toBe(
      "ws://127.0.0.1:54321/voice/vad/status"
    );
  });
});

describe("VoiceSocket", () => {
  it("starts in the connecting state", () => {
    FakeWebSocket.instances = [];
    const socket = new VoiceSocket("ws://test", {
      onMessage: vi.fn(),
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });
    expect(socket.state).toBe("connecting");
  });

  it("transitions to open when the underlying socket opens", () => {
    FakeWebSocket.instances = [];
    const socket = new VoiceSocket("ws://test", {
      onMessage: vi.fn(),
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });
    FakeWebSocket.instances[0].onopen?.();
    expect(socket.state).toBe("open");
  });

  it("parses JSON messages before handing them to onMessage", () => {
    FakeWebSocket.instances = [];
    const onMessage = vi.fn();
    new VoiceSocket("ws://test", {
      onMessage,
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });

    FakeWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ is_speech: true }) });
    expect(onMessage).toHaveBeenCalledWith({ is_speech: true });
  });

  it("falls back to raw data if a message isn't valid JSON", () => {
    FakeWebSocket.instances = [];
    const onMessage = vi.fn();
    new VoiceSocket("ws://test", {
      onMessage,
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });

    FakeWebSocket.instances[0].onmessage?.({ data: "not json" });
    expect(onMessage).toHaveBeenCalledWith("not json");
  });

  it("does not send while the socket is still connecting", () => {
    FakeWebSocket.instances = [];
    const socket = new VoiceSocket("ws://test", {
      onMessage: vi.fn(),
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });

    socket.sendBytes(new ArrayBuffer(4));
    expect(FakeWebSocket.instances[0].send).not.toHaveBeenCalled();
  });

  it("sends bytes once open", () => {
    FakeWebSocket.instances = [];
    const socket = new VoiceSocket("ws://test", {
      onMessage: vi.fn(),
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });
    FakeWebSocket.instances[0].onopen?.();

    const data = new ArrayBuffer(8);
    socket.sendBytes(data);
    expect(FakeWebSocket.instances[0].send).toHaveBeenCalledWith(data);
  });

  it("calls onClose when the socket closes", () => {
    FakeWebSocket.instances = [];
    const onClose = vi.fn();
    const socket = new VoiceSocket("ws://test", {
      onMessage: vi.fn(),
      onClose,
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });
    FakeWebSocket.instances[0].onopen?.();

    socket.close();
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(socket.state).toBe("closed");
  });

  it("close() is idempotent", () => {
    FakeWebSocket.instances = [];
    const socket = new VoiceSocket("ws://test", {
      onMessage: vi.fn(),
      WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    });
    FakeWebSocket.instances[0].onopen?.();

    socket.close();
    socket.close();
    expect(FakeWebSocket.instances[0].close).toHaveBeenCalledTimes(1);
  });
});
