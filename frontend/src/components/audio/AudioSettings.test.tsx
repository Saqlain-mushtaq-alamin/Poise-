import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AudioSettings } from "./AudioSettings";

const voices = [
  { id: "voice-a", name: "Voice A", language: "en", gender: "female", sample_url: null },
  { id: "voice-b", name: "Voice B", language: "en", gender: "male", sample_url: null },
];

function stubMediaDevices(devices: Partial<MediaDeviceInfo>[]) {
  vi.stubGlobal("navigator", {
    mediaDevices: {
      enumerateDevices: vi.fn().mockResolvedValue(devices),
    },
  });
}

describe("AudioSettings", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    stubMediaDevices([
      { deviceId: "mic-1", kind: "audioinput", label: "Built-in Mic" },
      { deviceId: "cam-1", kind: "videoinput", label: "Webcam" },
    ]);
  });

  it("lists only audio input devices, filtering out video devices", async () => {
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="idle"
        partialTranscript=""
        onPreviewVoice={vi.fn()}
        onTestTranscribe={vi.fn()}
        onStopTest={vi.fn()}
      />
    );

    await waitFor(() => expect(screen.getByText("Built-in Mic")).toBeInTheDocument());
    expect(screen.queryByText("Webcam")).not.toBeInTheDocument();
  });

  it("shows a fallback message when enumerateDevices isn't supported", async () => {
    vi.stubGlobal("navigator", {});
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="idle"
        partialTranscript=""
        onPreviewVoice={vi.fn()}
        onTestTranscribe={vi.fn()}
        onStopTest={vi.fn()}
      />
    );

    expect(await screen.findByText(/doesn't support listing audio devices/)).toBeInTheDocument();
  });

  it("defaults the voice picker to the first available voice", () => {
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="idle"
        partialTranscript=""
        onPreviewVoice={vi.fn()}
        onTestTranscribe={vi.fn()}
        onStopTest={vi.fn()}
      />
    );

    expect(screen.getByLabelText(/tts voice/i)).toHaveValue("voice-a");
  });

  it("calls onPreviewVoice with the selected voice id", () => {
    const onPreviewVoice = vi.fn();
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="idle"
        partialTranscript=""
        onPreviewVoice={onPreviewVoice}
        onTestTranscribe={vi.fn()}
        onStopTest={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    expect(onPreviewVoice).toHaveBeenCalledWith("voice-a");
  });

  it("shows the volume meter fill proportional to volumeLevel", () => {
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0.5}
        turnState="idle"
        partialTranscript=""
        onPreviewVoice={vi.fn()}
        onTestTranscribe={vi.fn()}
        onStopTest={vi.fn()}
      />
    );

    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "50");
  });

  it("calls onTestTranscribe when idle and the test button is clicked", () => {
    const onTestTranscribe = vi.fn();
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="idle"
        partialTranscript=""
        onPreviewVoice={vi.fn()}
        onTestTranscribe={onTestTranscribe}
        onStopTest={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /say something/i }));
    expect(onTestTranscribe).toHaveBeenCalled();
  });

  it("shows a Stop test button and current turn state while testing", () => {
    const onStopTest = vi.fn();
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="listening"
        partialTranscript=""
        onPreviewVoice={vi.fn()}
        onTestTranscribe={vi.fn()}
        onStopTest={onStopTest}
      />
    );

    expect(screen.getByText("(listening)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /stop test/i }));
    expect(onStopTest).toHaveBeenCalled();
  });

  it("renders the partial transcript when present", () => {
    render(
      <AudioSettings
        voices={voices}
        volumeLevel={0}
        turnState="listening"
        partialTranscript="hello world"
        onPreviewVoice={vi.fn()}
        onTestTranscribe={vi.fn()}
        onStopTest={vi.fn()}
      />
    );

    expect(screen.getByText("hello world")).toBeInTheDocument();
  });
});
