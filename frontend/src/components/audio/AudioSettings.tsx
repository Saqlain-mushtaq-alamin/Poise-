import { useEffect, useState } from "react";

import type { VoiceInfo } from "../../lib/types";
import type { TurnState } from "../../services/audio/TurnManager";

const STT_LANGUAGES = [
  { code: "auto", label: "Auto-detect" },
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "hi", label: "Hindi" },
  { code: "bn", label: "Bengali" },
];

interface AudioSettingsProps {
  voices: VoiceInfo[];
  volumeLevel: number;
  turnState: TurnState;
  partialTranscript: string;
  onPreviewVoice: (voiceId: string) => void;
  onTestTranscribe: () => void;
  onStopTest: () => void;
}

function volumeZone(level: number): "low" | "mid" | "high" {
  if (level > 0.6) return "high";
  if (level > 0.2) return "mid";
  return "low";
}

export function AudioSettings({
  voices,
  volumeLevel,
  turnState,
  partialTranscript,
  onPreviewVoice,
  onTestTranscribe,
  onStopTest,
}: AudioSettingsProps) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [selectedVoice, setSelectedVoice] = useState(voices[0]?.id ?? "");
  const [sttLanguage, setSttLanguage] = useState("auto");
  const [noiseGateSensitivity, setNoiseGateSensitivity] = useState(50);
  const [devicesError, setDevicesError] = useState<string | null>(null);

  useEffect(() => {
    if (voices.length > 0 && !selectedVoice) {
      setSelectedVoice(voices[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voices]);

  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
      setDevicesError("This browser doesn't support listing audio devices.");
      return;
    }
    navigator.mediaDevices
      .enumerateDevices()
      .then((all) => setDevices(all.filter((d) => d.kind === "audioinput")))
      .catch((err) => setDevicesError((err as Error).message));
  }, []);

  const isTesting = turnState !== "idle";

  return (
    <div className="settings-card">
      <h3>Audio</h3>

      <div className="audio-settings__row">
        <label htmlFor="mic-device">Microphone</label>
        {devicesError ? (
          <p className="settings-card__warning">{devicesError}</p>
        ) : (
          <select
            id="mic-device"
            value={selectedDeviceId}
            onChange={(e) => setSelectedDeviceId(e.target.value)}
          >
            <option value="">System default</option>
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Microphone ${d.deviceId.slice(0, 6)}`}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="audio-settings__row">
        <span>Input level</span>
        <div className="audio-settings__meter" role="meter" aria-valuenow={Math.round(volumeLevel * 100)}>
          <div
            className={`audio-settings__meter-fill audio-settings__meter-fill--${volumeZone(volumeLevel)}`}
            style={{ width: `${Math.min(volumeLevel * 100, 100)}%` }}
          />
        </div>
      </div>

      <div className="audio-settings__row">
        <label htmlFor="tts-voice">TTS voice</label>
        <div className="audio-settings__voice-picker">
          <select id="tts-voice" value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)}>
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => onPreviewVoice(selectedVoice)} disabled={!selectedVoice}>
            Preview
          </button>
        </div>
      </div>

      <div className="audio-settings__row">
        <label htmlFor="stt-language">STT language</label>
        <select id="stt-language" value={sttLanguage} onChange={(e) => setSttLanguage(e.target.value)}>
          {STT_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div className="audio-settings__row">
        <label htmlFor="noise-gate">Noise gate sensitivity</label>
        <input
          id="noise-gate"
          type="range"
          min={0}
          max={100}
          value={noiseGateSensitivity}
          onChange={(e) => setNoiseGateSensitivity(Number(e.target.value))}
        />
      </div>

      <div className="audio-settings__test">
        <button type="button" onClick={isTesting ? onStopTest : onTestTranscribe}>
          {isTesting ? "Stop test" : "Say something and see it transcribed"}
        </button>
        {isTesting && <span className="audio-settings__turn-state">({turnState})</span>}
        {partialTranscript && <p className="audio-settings__transcript">{partialTranscript}</p>}
      </div>
    </div>
  );
}
