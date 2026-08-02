import { useCallback, useEffect, useRef, useState } from "react";

import type { PoiseAPI } from "../lib/api";
import { float32ToPCM16Bytes } from "../lib/audio-encoding";
import { MicCapture } from "../services/audio/MicCapture";
import { TTSPlayback } from "../services/audio/TTSPlayback";
import { TurnManager, type TurnState } from "../services/audio/TurnManager";
import { buildVoiceSocketUrl, VoiceSocket } from "../services/audio/VoiceSocket";

interface UseVoicePipelineOptions {
  api: PoiseAPI | null;
  sidecarPort: number | null;
  onFinalTranscript?: (text: string) => void;
}

interface UseVoicePipelineResult {
  turnState: TurnState;
  volumeLevel: number;
  partialTranscript: string;
  error: string | null;
  isCapturing: boolean;
  startListening: () => Promise<void>;
  stopListening: () => void;
  speak: (text: string) => Promise<void>;
}

/**
 * This is orchestration glue over four already-independently-tested pieces
 * (MicCapture, TurnManager, TTSPlayback, VoiceSocket) — see each of their
 * own test files for the thorough unit coverage. What's specific to this
 * hook (routing mic frames into the turn manager, buffering audio for the
 * STT socket only while LISTENING, starting/stopping TTS on state changes)
 * is straightforward wiring, so it's covered more lightly here rather than
 * re-testing the pieces it composes.
 */
export function useVoicePipeline({
  api,
  sidecarPort,
  onFinalTranscript,
}: UseVoicePipelineOptions): UseVoicePipelineResult {
  const micRef = useRef<MicCapture | null>(null);
  const turnManagerRef = useRef<TurnManager | null>(null);
  const ttsPlaybackRef = useRef<TTSPlayback | null>(null);
  const sttSocketRef = useRef<VoiceSocket | null>(null);

  const [turnState, setTurnState] = useState<TurnState>("idle");
  const [volumeLevel, setVolumeLevel] = useState(0);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);

  const onFinalTranscriptRef = useRef(onFinalTranscript);
  onFinalTranscriptRef.current = onFinalTranscript;

  const getTtsPlayback = useCallback(() => {
    if (!ttsPlaybackRef.current) {
      ttsPlaybackRef.current = new TTSPlayback();
    }
    return ttsPlaybackRef.current;
  }, []);

  const getTurnManager = useCallback(() => {
    if (!turnManagerRef.current) {
      turnManagerRef.current = new TurnManager({
        onStateChange: (next) => setTurnState(next),
        onInterruptPlayback: () => getTtsPlayback().stop(),
      });
    }
    return turnManagerRef.current;
  }, [getTtsPlayback]);

  const getMic = useCallback(() => {
    if (!micRef.current) {
      micRef.current = new MicCapture();
    }
    return micRef.current;
  }, []);

  const startListening = useCallback(async () => {
    if (sidecarPort === null) {
      setError("Sidecar not connected yet");
      return;
    }

    const mic = getMic();
    const turnManager = getTurnManager();
    setError(null);

    const sttSocket = new VoiceSocket(buildVoiceSocketUrl(sidecarPort, "/voice/stt/stream"), {
      onMessage: (data) => {
        const msg = data as {
          error?: string;
          text?: string;
          is_partial?: boolean;
        };
        if (msg.error) {
          setError(msg.error);
          return;
        }
        if (typeof msg.text === "string") {
          setPartialTranscript(msg.text);
          if (!msg.is_partial) {
            onFinalTranscriptRef.current?.(msg.text);
          }
        }
      },
    });
    sttSocketRef.current = sttSocket;

    mic.addEventListener("volume-level", ((event: CustomEvent<number>) => {
      setVolumeLevel(event.detail);
    }) as EventListener);

    mic.addEventListener("vad-frame", ((
      event: CustomEvent<{ isSpeech: boolean; timestampMs: number }>
    ) => {
      turnManager.reportVadFrame(event.detail.isSpeech, event.detail.timestampMs);
    }) as EventListener);

    mic.addEventListener("audio-chunk", ((event: CustomEvent<Float32Array>) => {
      if (turnManager.state === "listening") {
        sttSocket.sendBytes(float32ToPCM16Bytes(event.detail));
      }
    }) as EventListener);

    try {
      await mic.start();
      setIsCapturing(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [sidecarPort, getMic, getTurnManager]);

  const stopListening = useCallback(() => {
    micRef.current?.stop();
    sttSocketRef.current?.close();
    sttSocketRef.current = null;
    setIsCapturing(false);
    getTurnManager().reset();
  }, [getTurnManager]);

  const speak = useCallback(
    async (text: string) => {
      if (!api) {
        setError("Sidecar not connected yet");
        return;
      }
      const turnManager = getTurnManager();
      const playback = getTtsPlayback();

      turnManager.startSpeaking();
      try {
        const stream = await api.synthesizeSpeechStream<ReadableStream<Uint8Array>>(text);
        playback.addEventListener(
          "playback-ended",
          () => {
            turnManager.endSpeaking();
          },
          { once: true }
        );
        await playback.playStream(stream);
      } catch (err) {
        setError((err as Error).message);
        turnManager.endSpeaking();
      }
    },
    [api, getTurnManager, getTtsPlayback]
  );

  useEffect(() => {
    return () => {
      micRef.current?.stop();
      sttSocketRef.current?.close();
      ttsPlaybackRef.current?.stop();
    };
  }, []);

  return {
    turnState,
    volumeLevel,
    partialTranscript,
    error,
    isCapturing,
    startListening,
    stopListening,
    speak,
  };
}
