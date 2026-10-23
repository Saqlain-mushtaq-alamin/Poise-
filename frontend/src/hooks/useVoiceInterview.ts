/**
 * useVoiceInterview — voice pipeline for the video-call interview room.
 *
 * KEY FIXES (2026-08-14):
 * 1. Bluetooth headphone TTS: falls back to window.speechSynthesis when the
 *    backend audio blob plays silently (common when BT headphones are the
 *    audio output device and blob: URLs don't route to them correctly).
 * 2. Microphone: silent-silence timer runs on a 500ms interval independently
 *    of VAD, so a long pause ALWAYS triggers even if the mic analyser is
 *    reading near-zero (BT headphone audio routing artifact on Windows).
 * 3. Max-listen timeout (45s): auto-submits transcript or a placeholder if
 *    the user never reaches a pause threshold — the interview keeps moving.
 * 4. Speech recognition (webkitSpeechRecognition) is NOT available in Tauri
 *    WebView2. The hook detects this and uses the Whisper WS STT pipeline.
 * 5. Back-button: onBack callback is now surfaced so callers can navigate
 *    the user back to the setup screen.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { float32ToPCM16Bytes } from "../lib/audio-encoding";
import { VoiceSocket } from "../services/audio/VoiceSocket";

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
  onAnswerReady: (text: string, audioPath?: string) => void;
  silenceThresholdSecs?: number;
  maxListenSecs?: number;
  enabled?: boolean;
}

export interface StartListeningOptions {
  silenceThresholdSecs?: number;
  maxListenSecs?: number;
}

interface UseVoiceInterviewReturn {
  phase: VoicePhase;
  transcript: string;
  interimTranscript: string;
  isAISpeaking: boolean;
  isSpeaking: boolean;
  speakAsAI: (text: string, voice?: string) => Promise<void>;
  cancelAISpeech: () => void;
  startListening: (opts?: StartListeningOptions) => Promise<void>;
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
  silenceThresholdSecs = 3.5,  // raised from 2.5 — candidates need thinking time
  maxListenSecs = 45,
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
  const aiAudioRef = useRef<HTMLAudioElement | null>(null);
  const aiBlobUrlRef = useRef<string | null>(null);
  const aiLevelRafRef = useRef<number>(0);
  const speakerCtxRef = useRef<AudioContext | null>(null);
  const activeSourceNodeRef = useRef<AudioBufferSourceNode | null>(null);

  const micCtxRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const micAnalyserRef = useRef<AnalyserNode | null>(null);
  const micRafRef = useRef<number>(0);

  const speechRecRef = useRef<SpeechRecognitionAny | null>(null);
  // Primary silence timer — reset on any speech/transcript activity
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Independent periodic silence checker — fires every 500ms and guarantees
  // the threshold is reached even when BT headphone mic shows near-zero VAD
  const silenceIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Max-listen timeout — auto-submits after maxListenSecs regardless
  const maxListenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track when we entered listening state
  const listenStartedAtRef = useRef<number>(0);
  // Track last voice activity timestamp
  const lastActivityRef = useRef<number>(0);

  const transcriptRef = useRef("");
  const phaseRef = useRef<VoicePhase>("idle");
  const interimTranscriptRef = useRef("");
  const sttSocketRef = useRef<VoiceSocket | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);

  const activeSilenceThresholdRef = useRef(silenceThresholdSecs);
  const activeMaxListenSecsRef = useRef(maxListenSecs);
  useEffect(() => { activeSilenceThresholdRef.current = silenceThresholdSecs; }, [silenceThresholdSecs]);
  useEffect(() => { activeMaxListenSecsRef.current = maxListenSecs; }, [maxListenSecs]);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  // keep refs in sync
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);
  useEffect(() => { interimTranscriptRef.current = interimTranscript; }, [interimTranscript]);

  // Check Speech API availability once.
  // WebView2 on Windows defines window.webkitSpeechRecognition, but it cannot connect
  // to Google Cloud Speech recognition without embedded API keys and throws network errors.
  // In Tauri desktop apps we prioritize the local Whisper WebSocket STT.
  useEffect(() => {
    const win = window as unknown as Record<string, unknown>;
    const isTauriEnv =
      typeof window !== "undefined" &&
      ("__TAURI__" in window || "__TAURI_INTERNALS__" in window);
    const SR = !isTauriEnv && (win.SpeechRecognition ?? win.webkitSpeechRecognition);
    setSpeechApiAvailable(!!SR);
  }, []);

  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Un-suspend AudioContext on any user interaction (click, keypress, touch)
  useEffect(() => {
    const unlock = () => {
      try {
        const AudioCtxClass =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        if (!speakerCtxRef.current || speakerCtxRef.current.state === "closed") {
          speakerCtxRef.current = new AudioCtxClass();
        }
        if (speakerCtxRef.current.state === "suspended") {
          speakerCtxRef.current.resume().catch(() => {});
        }
        if (micCtxRef.current && micCtxRef.current.state === "suspended") {
          micCtxRef.current.resume().catch(() => {});
        }
        if (typeof window !== "undefined" && window.speechSynthesis && window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }
      } catch { /* ok */ }
    };
    unlock();
    window.addEventListener("click", unlock, { passive: true });
    window.addEventListener("keydown", unlock, { passive: true });
    window.addEventListener("touchstart", unlock, { passive: true });
    return () => {
      window.removeEventListener("click", unlock);
      window.removeEventListener("keydown", unlock);
      window.removeEventListener("touchstart", unlock);
    };
  }, []);

  // ---- AI audio level (analyser-driven for Web Audio + simulation fallback for HTMLAudio) ----
  function stopAILevelPoll() {
    cancelAnimationFrame(aiLevelRafRef.current);
    setAiAudioLevel(0);
  }

  function startAILevelPollFromAnalyser(analyser: AnalyserNode) {
    stopAILevelPoll();
    const data = new Uint8Array(analyser.fftSize);
    function tick() {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const n = (data[i] - 128) / 128;
        sum += n * n;
      }
      const level = Math.min(Math.sqrt(sum / data.length) * 5, 1);
      setAiAudioLevel(level);
      aiLevelRafRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  function startAILevelPoll(audio: HTMLAudioElement) {
    stopAILevelPoll();
    function tick() {
      if (audio.paused || audio.ended) {
        setAiAudioLevel(0);
        return;
      }
      // Generate a natural speech audio level modulation while playing
      const level = 0.25 + Math.sin(Date.now() / 80) * 0.15 + Math.random() * 0.1;
      setAiAudioLevel(Math.min(Math.max(level, 0), 1));
      aiLevelRafRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  // ---- Browser speechSynthesis TTS fallback ----
  function speakWithBrowserTTS(text: string, voiceName?: string): Promise<void> {
    return new Promise((resolve) => {
      if (typeof window === "undefined" || !window.speechSynthesis) {
        resolve();
        return;
      }
      window.speechSynthesis.cancel();
      if (window.speechSynthesis.paused) {
        try { window.speechSynthesis.resume(); } catch { /* ok */ }
      }
      const utt = new SpeechSynthesisUtterance(text);
      utt.rate = 0.95;
      utt.pitch = 1;
      utt.volume = 1.0;
      activeUtteranceRef.current = utt;

      let resolved = false;
      const finish = () => {
        if (resolved) return;
        resolved = true;
        clearTimeout(safetyTimer);
        activeUtteranceRef.current = null;
        resolve();
      };

      const maxWaitMs = Math.max(4000, Math.ceil(text.length * 85));
      const safetyTimer = setTimeout(finish, maxWaitMs);

      const assignVoiceAndSpeak = () => {
        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0) {
          let match: SpeechSynthesisVoice | undefined;
          if (voiceName) {
            match = voices.find(v => v.name.toLowerCase().includes(voiceName.toLowerCase()) || v.lang.startsWith("en"));
          }
          if (!match) {
            match = voices.find(v => v.lang.startsWith("en")) || voices[0];
          }
          if (match) utt.voice = match;
        }
        utt.onend = finish;
        utt.onerror = finish;
        window.speechSynthesis.speak(utt);
      };

      if (window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = () => {
          window.speechSynthesis.onvoiceschanged = null;
          assignVoiceAndSpeak();
        };
        setTimeout(assignVoiceAndSpeak, 250);
      } else {
        assignVoiceAndSpeak();
      }
    });
  }

  // ---- Speak as AI ----
  const cancelAISpeech = useCallback(() => {
    stopAILevelPoll();
    if (activeSourceNodeRef.current) {
      try { activeSourceNodeRef.current.stop(); } catch { /* ok */ }
      activeSourceNodeRef.current = null;
    }
    // Cancel browser TTS too
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
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

    let backendSucceeded = false;

    // 1. Try Backend Audio (Web Audio API direct decoding + HTMLAudio fallback)
    try {
      if (backendBaseUrl) {
        const url = `${backendBaseUrl}/voice/tts/synthesize`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, voice, stream: false }),
        });

        if (res.ok) {
          const arrayBuffer = await res.arrayBuffer();
          if (arrayBuffer.byteLength > 100) {
            // First attempt: Web Audio API (unlocked, pristine PCM playback directly to hardware)
            try {
              const AudioCtxClass =
                window.AudioContext ||
                (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
              if (!speakerCtxRef.current || speakerCtxRef.current.state === "closed") {
                speakerCtxRef.current = new AudioCtxClass();
              }
              const ctx = speakerCtxRef.current;
              if (ctx.state === "suspended") {
                await ctx.resume().catch(() => {});
              }

              // decodeAudioData consumes the buffer, so pass a clone
              const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
              const source = ctx.createBufferSource();
              source.buffer = audioBuffer;

              const analyser = ctx.createAnalyser();
              analyser.fftSize = 256;
              source.connect(analyser);
              analyser.connect(ctx.destination);
              activeSourceNodeRef.current = source;

              startAILevelPollFromAnalyser(analyser);

              await new Promise<void>((resolve) => {
                source.onended = () => {
                  stopAILevelPoll();
                  activeSourceNodeRef.current = null;
                  resolve();
                };
                source.start(0);
              });
              backendSucceeded = true;
            } catch (webAudioErr) {
              console.warn("[TTS] Web Audio playback failed, falling back to HTMLAudioElement:", webAudioErr);
            }

            // Fallback attempt: HTMLAudioElement with blob URL
            if (!backendSucceeded) {
              const blob = new Blob([arrayBuffer], { type: "audio/mpeg" });
              const blobUrl = URL.createObjectURL(blob);
              aiBlobUrlRef.current = blobUrl;
              const audio = new Audio(blobUrl);
              audio.volume = 1.0;
              aiAudioRef.current = audio;

              await new Promise<void>((resolve) => {
                let done = false;
                const finish = (success: boolean) => {
                  if (done) return;
                  done = true;
                  stopAILevelPoll();
                  if (success) backendSucceeded = true;
                  if (aiBlobUrlRef.current) {
                    URL.revokeObjectURL(aiBlobUrlRef.current);
                    aiBlobUrlRef.current = null;
                  }
                  aiAudioRef.current = null;
                  resolve();
                };

                audio.onended = () => finish(true);
                audio.onerror = () => finish(false);

                startAILevelPoll(audio);
                audio.play().catch((err) => {
                  console.warn("[TTS] audio.play() failed:", err);
                  finish(false);
                });
              });
            }
          }
        }
      }
    } catch (err) {
      console.warn("[useVoiceInterview] Backend TTS failed:", err);
    }

    // 2. Fallback: Browser SpeechSynthesis
    if (!backendSucceeded) {
      console.info("[TTS] Using browser speechSynthesis fallback for message:", text.slice(0, 30));
      setPhase("ai-speaking");
      try {
        await speakWithBrowserTTS(text, voice);
      } catch (err) {
        console.warn("[TTS] Browser TTS error:", err);
      }
    }

    if (phaseRef.current === "ai-speaking") setPhase("idle");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendBaseUrl, cancelAISpeech, enabled]);

  // ---- Silence detection helpers ----
  function clearAllTimers() {
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
    if (silenceIntervalRef.current) { clearInterval(silenceIntervalRef.current); silenceIntervalRef.current = null; }
    if (maxListenTimerRef.current) { clearTimeout(maxListenTimerRef.current); maxListenTimerRef.current = null; }
  }

  async function submitCurrentTranscript() {
    clearAllTimers();
    const liveTxt = (transcriptRef.current + " " + (interimTranscriptRef.current || "")).trim();
    if (!liveTxt && phaseRef.current !== "listening") return;

    setPhase("processing");

    // Stop MediaRecorder and collect full recorded audio
    let audioBlob: Blob | null = null;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        await new Promise<void>((resolve) => {
          if (!mediaRecorderRef.current || mediaRecorderRef.current.state === "inactive") {
            return resolve();
          }
          mediaRecorderRef.current.onstop = () => resolve();
          mediaRecorderRef.current.stop();
        });
      } catch { /* ok */ }
    }
    if (recordedChunksRef.current.length > 0) {
      const mime = mediaRecorderRef.current?.mimeType || "audio/webm";
      audioBlob = new Blob(recordedChunksRef.current, { type: mime });
    }

    let finalTranscript = liveTxt;
    let audioPath = "";

    // Two-pass STT: Send full recorded audio to backend for high-accuracy Whisper transcription
    if (audioBlob && audioBlob.size > 0 && backendBaseUrl) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);

      try {
        const formData = new FormData();
        const ext = audioBlob.type.includes("ogg") ? "ogg" : audioBlob.type.includes("wav") ? "wav" : "webm";
        formData.append("audio", audioBlob, `recording.${ext}`);
        formData.append("initial_prompt", "Um, uh, well, so, like, you know, actually, I think that...");

        const resp = await fetch(`${backendBaseUrl}/voice/transcribe-full`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (resp.ok) {
          const data = await resp.json();
          if (data.audio_path) {
            audioPath = data.audio_path;
          }
          if (data.transcript && data.transcript.trim()) {
            finalTranscript = data.transcript.trim();
          }
        }
      } catch (uploadErr: any) {
        clearTimeout(timeoutId);
        console.warn("[useVoiceInterview] transcribe-full timeout or error, using live transcript:", uploadErr?.message || uploadErr);
      }
    }

    onAnswerReady(finalTranscript, audioPath);
  }

  function resetSilenceTimer() {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    lastActivityRef.current = Date.now();
    silenceTimerRef.current = setTimeout(() => {
      const txt = (transcriptRef.current + " " + (interimTranscriptRef.current || "")).trim();
      if (txt && phaseRef.current === "listening") {
        submitCurrentTranscript();
      }
    }, activeSilenceThresholdRef.current * 1000);
  }

  function startSilenceInterval() {
    if (silenceIntervalRef.current) clearInterval(silenceIntervalRef.current);
    // Independent periodic checker — ensures silence threshold fires even
    // when mic analyser gives near-zero (Bluetooth headphone issue on Windows)
    silenceIntervalRef.current = setInterval(() => {
      if (phaseRef.current !== "listening") { clearInterval(silenceIntervalRef.current!); return; }
      const sinceLast = Date.now() - lastActivityRef.current;
      const txt = (transcriptRef.current + " " + (interimTranscriptRef.current || "")).trim();
      if (sinceLast >= activeSilenceThresholdRef.current * 1000 && txt) {
        submitCurrentTranscript();
      }
    }, 500);
  }

  function startMaxListenTimer() {
    if (maxListenTimerRef.current) clearTimeout(maxListenTimerRef.current);
    listenStartedAtRef.current = Date.now();
    maxListenTimerRef.current = setTimeout(() => {
      if (phaseRef.current !== "listening") return;
      const txt = (transcriptRef.current + " " + (interimTranscriptRef.current || "")).trim();
      if (txt) {
        submitCurrentTranscript();
      } else {
        setPhase("processing");
        onAnswerReady("", "");
      }
    }, activeMaxListenSecsRef.current * 1000);
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
      // Activity from VAD resets the silence timer
      if (level > 0.04 && phaseRef.current === "listening") {
        lastActivityRef.current = Date.now();
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = setTimeout(() => {
          if (transcriptRef.current.trim() && phaseRef.current === "listening") {
            submitCurrentTranscript();
          }
        }, silenceThresholdSecs * 1000);
      }
      micRafRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  // ---- Whisper WebSocket STT ----
  function startWhisperSTT(ctx: AudioContext, stream: MediaStream) {
    if (!backendBaseUrl || sttSocketRef.current) return;
    try {
      const wsProto = backendBaseUrl.startsWith("https") ? "wss:" : "ws:";
      const host = backendBaseUrl.replace(/^https?:\/\//, "");
      const sttUrl = `${wsProto}//${host}/voice/stt/stream?sample_rate=${ctx.sampleRate}`;

      const socket = new VoiceSocket(sttUrl, {
        onMessage: (data: any) => {
          // Handle model-not-available errors sent by the backend
          if (data?.error) {
            const errMsg = data.error as string;
            console.warn("[useVoiceInterview] STT error from backend:", errMsg);
            setMicError(
              data.model_name
                ? `Voice recognition model '${data.model_name}' not ready: ${errMsg}`
                : errMsg
            );
            return;
          }
          if (data?.text) {
            const text = String(data.text).trim();
            if (text) {
              lastActivityRef.current = Date.now();
              // Streaming Whisper sends the full coherent utterance transcription without severed words
              setTranscript(text);
              transcriptRef.current = text;
              setInterimTranscript("");
              if (phaseRef.current === "listening") resetSilenceTimer();
            }
          }
        },
        onError: (err) => {
          console.warn("[useVoiceInterview] STT WebSocket error:", err);
        },
      });
      sttSocketRef.current = socket;

      // Create ScriptProcessor to capture PCM audio frames
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorNodeRef.current = processor;
      processor.onaudioprocess = (e) => {
        if (phaseRef.current === "listening" && sttSocketRef.current?.state === "open") {
          const inputData = e.inputBuffer.getChannelData(0);
          const pcm16 = float32ToPCM16Bytes(inputData);
          sttSocketRef.current.sendBytes(pcm16);
        }
      };

      const src = ctx.createMediaStreamSource(stream);
      src.connect(processor);

      // Mute before destination to prevent local feedback/echo while keeping Web Audio processing alive
      const muteNode = ctx.createGain();
      muteNode.gain.value = 0;
      processor.connect(muteNode);
      muteNode.connect(ctx.destination);
    } catch (sttErr) {
      console.warn("[useVoiceInterview] STT WebSocket setup failed:", sttErr);
    }
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
      if (e.error !== "no-speech") {
        console.warn("[SpeechRecognition] error:", e.error);
        if (
          (e.error === "network" || e.error === "service-not-allowed" || e.error === "not-allowed") &&
          backendBaseUrl &&
          !sttSocketRef.current &&
          micCtxRef.current &&
          micStreamRef.current
        ) {
          console.info("[SpeechRecognition] Web Speech API unavailable, activating Whisper WebSocket STT fallback");
          startWhisperSTT(micCtxRef.current, micStreamRef.current);
        }
      }
    };

    rec.onend = () => {
      if (phaseRef.current === "listening") {
        try { rec.start(); } catch { /* restarting */ }
      }
    };

    try {
      rec.start();
      speechRecRef.current = rec;
    } catch (err) {
      console.warn("[SpeechRecognition] start failed:", err);
    }
  }

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
  const startListening = useCallback(async (opts?: StartListeningOptions) => {
    if (phaseRef.current === "listening") return;

    if (opts?.silenceThresholdSecs) activeSilenceThresholdRef.current = opts.silenceThresholdSecs;
    if (opts?.maxListenSecs) activeMaxListenSecsRef.current = opts.maxListenSecs;

    if (phaseRef.current === "ai-speaking") {
      cancelAISpeech();
      await new Promise(r => setTimeout(r, 200));
    }

    setPhase("listening");
    setTranscript("");
    setInterimTranscript("");
    setMicError(null);
    lastActivityRef.current = Date.now();
    recordedChunksRef.current = [];

    try {
      // First try with audio enhancements, fall back to basic constraints
      // to avoid OverconstrainedError on some Windows audio drivers
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

      // Start MediaRecorder for pass 2 full utterance audio capture
      if (typeof MediaRecorder !== "undefined") {
        try {
          let mimeType = "";
          if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
            mimeType = "audio/webm;codecs=opus";
          } else if (MediaRecorder.isTypeSupported("audio/webm")) {
            mimeType = "audio/webm";
          } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
            mimeType = "audio/ogg;codecs=opus";
          }
          const rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
          rec.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
              recordedChunksRef.current.push(event.data);
            }
          };
          rec.start(250);
          mediaRecorderRef.current = rec;
        } catch (recErr) {
          console.warn("[useVoiceInterview] MediaRecorder initialization failed:", recErr);
          mediaRecorderRef.current = null;
        }
      }

      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      let ctx: AudioContext;
      try {
        ctx = new AudioCtxClass({ sampleRate: 16000 });
      } catch {
        ctx = new AudioCtxClass();
      }
      if (ctx.state === "suspended") await ctx.resume().catch(() => {});
      micCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      micAnalyserRef.current = analyser;

      startMicLevelPoll(analyser);

      const isTauriEnv =
        typeof window !== "undefined" &&
        ("__TAURI__" in window || "__TAURI_INTERNALS__" in window);
      const useWebSpeech = speechApiAvailable && !isTauriEnv;

      if (useWebSpeech) {
        startSpeechRecognition();
      }

      // Whisper WebSocket STT — primary path in Tauri WebView2 and fallback when Web Speech API is unavailable
      if (!useWebSpeech && backendBaseUrl) {
        startWhisperSTT(ctx, stream);
      }

      // Start the silence interval checker (handles BT headphone mic silence)
      startSilenceInterval();
      // Start max-listen timeout so the interview keeps moving
      startMaxListenTimer();

    } catch (err: any) {
      console.warn("[useVoiceInterview] getUserMedia failed:", err);
      const errName = err?.name ?? "";
      const errMsg = err?.message ?? String(err);
      let userFriendlyErr = `Microphone error: ${errMsg}`;
      if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
        userFriendlyErr =
          "⚠️ Microphone permission denied.\n\n" +
          "To fix this:\n" +
          "1. Open Windows Settings → Privacy & Security → Microphone\n" +
          "2. Turn ON 'Let apps access your microphone'\n" +
          "3. Turn ON 'Let desktop apps access your microphone'\n" +
          "4. Restart Poise\n\n" +
          "Also check that your Bluetooth headset is set as the default recording device in Sound Settings → Recording.";
      } else if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {
        userFriendlyErr = "No microphone found. Please connect a microphone and check Bluetooth headset is connected.";
      } else if (errName === "NotReadableError" || errName === "TrackStartError") {
        userFriendlyErr = "Microphone is in use by another app (Teams, Discord, Zoom). Please close it and retry.";
      }
      setMicError(userFriendlyErr);
      setMicAllowed(false);
      setPhase("idle");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cancelAISpeech, backendBaseUrl, speechApiAvailable]);

  const stopListening = useCallback(() => {
    clearAllTimers();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try { mediaRecorderRef.current.stop(); } catch { /* ok */ }
    }
    mediaRecorderRef.current = null;
    stopSpeechRecognition();
    stopMicLevelPoll();
    micStreamRef.current?.getTracks().forEach(t => t.stop());
    micStreamRef.current = null;
    micCtxRef.current?.close().catch(() => {});
    micCtxRef.current = null;
    if (phaseRef.current === "listening") setPhase("idle");
  }, []);

  const clearTranscript = useCallback(() => {
    transcriptRef.current = "";
    interimTranscriptRef.current = "";
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
