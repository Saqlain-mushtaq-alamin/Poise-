/**
 * useVoiceInterview — voice pipeline for the video-call interview room.
 *
 * KEY DESIGN DECISIONS:
 * - Audio is played via HTMLAudioElement + Blob URL (not AudioContext) to
 *   avoid the browser autoplay-policy block and WAV-chunk decode issues.
 * - Web Speech API handles live transcription (Chromium-based, works in
 *   Tauri/WebView). Falls back gracefully when unavailable.
 * - Silence detection is done by the mic energy analyser (AudioContext ←
 *   mic stream) + a configurable timer, not the backend VAD WebSocket
 *   (simpler, zero extra round-trips).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { float32ToPCM16Bytes } from "../lib/audio-encoding";
import { VoiceSocket } from "../services/audio/VoiceSocket";

// Web Speech API ambient types
/* eslint-disable @typescript-eslint/no-explicit-any */
type SpeechRecognitionAny = any;

export type VoicePhase =
  | "idle"
  | "ai-speaking"
  | "listening"
  | "processing"
  | "paused";

interface UseVoiceInterviewOptions {
  backendBaseUrl: string;
  onAnswerReady: (text: string) => void;
  silenceThresholdSecs?: number;
  enabled?: boolean;
}

interface UseVoiceInterviewReturn {
  phase: VoicePhase;
  transcript: string;
  interimTranscript: string;
  isAISpeaking: boolean;
  isSpeaking: boolean;
  speakAsAI: (text: string, voice?: string) => Promise<void>;
  cancelAISpeech: () => void;
  startListening: () => void;
  stopListening: () => void;
  clearTranscript: () => void;
  vadLevel: number;
  aiAudioLevel: number;
  micAllowed: boolean;
  speechApiAvailable: boolean;
  micError: string | null;
}

export function useVoiceInterview({
  backendBaseUrl,
  onAnswerReady,
  silenceThresholdSecs = 2.5,
  enabled = true,
}: UseVoiceInterviewOptions): UseVoiceInterviewReturn {
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [vadLevel, setVadLevel] = useState(0);
  const [aiAudioLevel, setAiAudioLevel] = useState(0);
  const [micAllowed, setMicAllowed] = useState(false);
  const [speechApiAvailable, setSpeechApiAvailable] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  // ---- refs ----
  // HTMLAudioElement for AI TTS — avoids AudioContext autoplay block
  const aiAudioRef = useRef<HTMLAudioElement | null>(null);
  const aiBlobUrlRef = useRef<string | null>(null);
  const aiLevelRafRef = useRef<number>(0);

  // AudioContext used ONLY for mic analysis (after getUserMedia, which
  // itself requires a user gesture so AudioContext is already unlocked)
  const micCtxRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const micAnalyserRef = useRef<AnalyserNode | null>(null);
  const micRafRef = useRef<number>(0);

  const speechRecRef = useRef<SpeechRecognitionAny | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptRef = useRef("");
  const phaseRef = useRef<VoicePhase>("idle");

  // keep refs in sync
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  // Check Speech API availability once
  useEffect(() => {
    const SR =
      (window as unknown as Record<string, unknown>).SpeechRecognition ??
      (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
    setSpeechApiAvailable(!!SR);
  }, []);

  // ---- AI audio level (from HTMLAudioElement via AudioContext analyser) ----
  function stopAILevelPoll() {
    cancelAnimationFrame(aiLevelRafRef.current);
    setAiAudioLevel(0);
  }

  async function startAILevelPoll(audio: HTMLAudioElement) {
    // Create a one-time AudioContext just for visualisation
    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtxClass();
      if (ctx.state === "suspended") {
        await ctx.resume().catch(() => {});
      }
      const src = ctx.createMediaElementSource(audio);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      analyser.connect(ctx.destination);
      const buf = new Uint8Array(analyser.fftSize);
      function tick() {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const n = (buf[i] - 128) / 128;
          sum += n * n;
        }
        setAiAudioLevel(Math.min(Math.sqrt(sum / buf.length) * 5, 1));
        aiLevelRafRef.current = requestAnimationFrame(tick);
      }
      tick();
      // Cleanup ctx when audio ends
      audio.addEventListener("ended", () => ctx.close().catch(() => {}), { once: true });
    } catch (err) {
      console.warn("[useVoiceInterview] AI audio level poll setup failed:", err);
    }
  }

  // ---- Speak as AI ----
  const cancelAISpeech = useCallback(() => {
    stopAILevelPoll();
    if (aiAudioRef.current) {
      aiAudioRef.current.pause();
      aiAudioRef.current.src = "";
      aiAudioRef.current = null;
    }
    if (aiBlobUrlRef.current) {
      URL.revokeObjectURL(aiBlobUrlRef.current);
      aiBlobUrlRef.current = null;
    }
    if (phaseRef.current === "ai-speaking") setPhase("idle");
  }, []);

  const speakAsAI = useCallback(async (text: string, voice = "en-US-AvaNeural") => {
    if (!enabled || !text.trim()) return;
    cancelAISpeech();
    setPhase("ai-speaking");

    try {
      const url = `${backendBaseUrl}/voice/tts/synthesize`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice, stream: false }),
      });

      if (!res.ok) throw new Error(`TTS ${res.status}`);

      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      aiBlobUrlRef.current = blobUrl;

      const audio = new Audio(blobUrl);
      aiAudioRef.current = audio;

      audio.onended = () => {
        stopAILevelPoll();
        URL.revokeObjectURL(blobUrl);
        aiBlobUrlRef.current = null;
        if (phaseRef.current === "ai-speaking") setPhase("idle");
      };

      audio.onerror = () => {
        stopAILevelPoll();
        setPhase("idle");
      };

      startAILevelPoll(audio);
      await audio.play();
    } catch (err) {
      console.warn("[useVoiceInterview] TTS failed:", err);
      setPhase("idle");
    }
  }, [backendBaseUrl, cancelAISpeech, enabled]);

  // ---- Silence timer ----
  function clearSilenceTimer() {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }

  function resetSilenceTimer() {
    clearSilenceTimer();
    silenceTimerRef.current = setTimeout(() => {
      const txt = transcriptRef.current.trim();
      if (txt && phaseRef.current === "listening") {
        setPhase("processing");
        onAnswerReady(txt);
      }
    }, silenceThresholdSecs * 1000);
  }

  // ---- Mic level polling ----
  function stopMicLevelPoll() {
    cancelAnimationFrame(micRafRef.current);
    setVadLevel(0);
  }

  function startMicLevelPoll(analyser: AnalyserNode) {
    const buf = new Uint8Array(analyser.fftSize);
    function tick() {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const n = (buf[i] - 128) / 128;
        sum += n * n;
      }
      const level = Math.min(Math.sqrt(sum / buf.length) * 6, 1);
      setVadLevel(level);
      // Any activity → reset silence window
      if (level > 0.04 && phaseRef.current === "listening") resetSilenceTimer();
      micRafRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  // ---- Web Speech API ----
  function startSpeechRecognition() {
    const win = window as unknown as Record<string, any>;
    const SR = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!SR) return;

    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.maxAlternatives = 1;

    rec.onresult = (e: any) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const chunk = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          final += chunk + " ";
        } else {
          interim += chunk;
        }
      }
      if (final) {
        setTranscript(prev => (prev + " " + final).trim());
        if (phaseRef.current === "listening") resetSilenceTimer();
      }
      setInterimTranscript(interim);
    };

    rec.onerror = (e: any) => {
      // "no-speech" is normal — don't stop listening
      if (e.error !== "no-speech") {
        console.warn("[SpeechRecognition] error:", e.error);
      }
    };

    rec.onend = () => {
      // Auto-restart if still listening (browser stops recognition after ~60s)
      if (phaseRef.current === "listening") {
        try { rec.start(); } catch { /* already restarting */ }
      }
    };

    try {
      rec.start();
      speechRecRef.current = rec;
    } catch (err) {
      console.warn("[SpeechRecognition] start failed:", err);
    }
  }

  const sttSocketRef = useRef<VoiceSocket | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);

  function stopSpeechRecognition() {
    if (speechRecRef.current) {
      try { speechRecRef.current.stop(); } catch { /* ok */ }
      speechRecRef.current = null;
    }
    if (processorNodeRef.current) {
      try { processorNodeRef.current.disconnect(); } catch { /* ok */ }
      processorNodeRef.current = null;
    }
    if (sttSocketRef.current) {
      try { sttSocketRef.current.close(); } catch { /* ok */ }
      sttSocketRef.current = null;
    }
    setInterimTranscript("");
  }

  // ---- Start / stop listening ----
  const startListening = useCallback(async () => {
    if (phaseRef.current === "listening") return;

    // Stop any ongoing AI audio first
    if (phaseRef.current === "ai-speaking") {
      cancelAISpeech();
      await new Promise(r => setTimeout(r, 200));
    }

    setPhase("listening");
    setTranscript("");
    setInterimTranscript("");
    setMicError(null);

    try {
      // Avoid hardcoded sampleRate in getUserMedia constraints on Windows as hardware drivers can reject it with OverconstrainedError
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      micStreamRef.current = stream;
      setMicAllowed(true);

      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtxClass();
      if (ctx.state === "suspended") {
        await ctx.resume().catch(() => {});
      }
      micCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      micAnalyserRef.current = analyser;

      startMicLevelPoll(analyser);
      startSpeechRecognition();

      // Fallback: If Web Speech API is absent (such as in Tauri WebView2), use backend Whisper STT WebSocket stream
      if (!speechApiAvailable && backendBaseUrl) {
        try {
          const wsProto = backendBaseUrl.startsWith("https") ? "wss:" : "ws:";
          const host = backendBaseUrl.replace(/^https?:\/\//, "");
          const sttUrl = `${wsProto}//${host}/voice/stt/stream`;

          const socket = new VoiceSocket(sttUrl, {
            onMessage: (data: any) => {
              if (data?.text) {
                if (data.is_partial) {
                  setInterimTranscript(data.text);
                } else {
                  setTranscript(prev => (prev + " " + data.text).trim());
                  setInterimTranscript("");
                  if (phaseRef.current === "listening") resetSilenceTimer();
                }
              }
            },
          });
          sttSocketRef.current = socket;

          const processor = ctx.createScriptProcessor(4096, 1, 1);
          processorNodeRef.current = processor;
          processor.onaudioprocess = (e) => {
            if (phaseRef.current === "listening" && sttSocketRef.current?.state === "open") {
              const inputData = e.inputBuffer.getChannelData(0);
              const pcm16 = float32ToPCM16Bytes(inputData);
              sttSocketRef.current.sendBytes(pcm16);
            }
          };
          src.connect(processor);
          processor.connect(ctx.destination);
        } catch (sttErr) {
          console.warn("[useVoiceInterview] STT WebSocket setup failed:", sttErr);
        }
      }

      resetSilenceTimer(); // start counting silence immediately
    } catch (err: any) {
      console.warn("[useVoiceInterview] getUserMedia failed:", err);
      const errName = err?.name ?? "";
      const errMsg = err?.message ?? String(err);
      let userFriendlyErr = `Microphone error: ${errMsg}`;
      if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
        userFriendlyErr =
          "Microphone permission denied. Please allow microphone access in Windows Settings → Privacy & Security → Microphone, and ensure 'Let desktop apps access your microphone' is ON.";
      } else if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {
        userFriendlyErr = "No microphone found. Please connect a microphone to your computer.";
      } else if (errName === "NotReadableError" || errName === "TrackStartError") {
        userFriendlyErr = "Microphone is in use by another application (e.g. Teams, Discord, Zoom).";
      }
      setMicError(userFriendlyErr);
      setMicAllowed(false);
      setPhase("idle");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cancelAISpeech, backendBaseUrl, speechApiAvailable]);

  const stopListening = useCallback(() => {
    clearSilenceTimer();
    stopSpeechRecognition();
    stopMicLevelPoll();
    micStreamRef.current?.getTracks().forEach(t => t.stop());
    micStreamRef.current = null;
    micCtxRef.current?.close().catch(() => {});
    micCtxRef.current = null;
    if (phaseRef.current === "listening") setPhase("idle");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscript("");
    setInterimTranscript("");
  }, []);

  // ---- Cleanup on unmount ----
  useEffect(() => {
    return () => {
      cancelAISpeech();
      stopListening();
    };
  }, [cancelAISpeech, stopListening]);

  return {
    phase,
    transcript,
    interimTranscript,
    isAISpeaking: phase === "ai-speaking",
    isSpeaking: vadLevel > 0.04,
    speakAsAI,
    cancelAISpeech,
    startListening,
    stopListening,
    clearTranscript,
    vadLevel,
    aiAudioLevel,
    micAllowed,
    speechApiAvailable,
    micError,
  };
}
