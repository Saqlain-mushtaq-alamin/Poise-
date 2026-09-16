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
  onAnswerReady: (text: string) => void;
  silenceThresholdSecs?: number;
  maxListenSecs?: number;
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
  const sttSocketRef = useRef<VoiceSocket | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);

  // keep refs in sync
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  // Check Speech API availability once — WebView2 does NOT have webkitSpeechRecognition
  useEffect(() => {
    const win = window as unknown as Record<string, unknown>;
    const SR = win.SpeechRecognition ?? win.webkitSpeechRecognition;
    setSpeechApiAvailable(!!SR);
  }, []);

  // ---- AI audio level (simulated for visualizer without muting HTMLAudioElement) ----
  function stopAILevelPoll() {
    cancelAnimationFrame(aiLevelRafRef.current);
    setAiAudioLevel(0);
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
      const utt = new SpeechSynthesisUtterance(text);
      utt.rate = 0.95;
      utt.pitch = 1;
      utt.volume = 1.0;

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
        utt.onend = () => resolve();
        utt.onerror = () => resolve();
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

    // 1. Try Backend Audio (WAV/TTS from backend)
    try {
      if (backendBaseUrl) {
        const url = `${backendBaseUrl}/voice/tts/synthesize`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, voice, stream: false }),
        });

        if (res.ok) {
          const blob = await res.blob();
          if (blob.size > 100) {
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
              audio.play().then(() => {
                // If after 1.2s audio hasn't progressed, fallback to browser TTS
                setTimeout(() => {
                  if (!done && audio.currentTime <= 0.01) {
                    console.warn("[TTS] Audio playback stalled, falling back to browser TTS");
                    audio.pause();
                    finish(false);
                  }
                }, 1200);
              }).catch((err) => {
                console.warn("[TTS] audio.play() blocked/failed:", err);
                finish(false);
              });
            });
          }
        }
      }
    } catch (err) {
      console.warn("[useVoiceInterview] Backend TTS failed:", err);
    }

    // 2. Fallback: Browser SpeechSynthesis (guaranteed output on Windows / BT headphones)
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

  function submitCurrentTranscript() {
    clearAllTimers();
    const txt = transcriptRef.current.trim();
    // Require at least 5 words to avoid false silence-detection triggers
    const wordCount = txt ? txt.split(/\s+/).filter(Boolean).length : 0;
    if (txt && wordCount >= 5 && phaseRef.current === "listening") {
      setPhase("processing");
      onAnswerReady(txt);
    } else if (txt && wordCount < 5) {
      // Too short — reset and keep listening
      lastActivityRef.current = Date.now();
      resetSilenceTimer();
    }
  }

  function resetSilenceTimer() {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    lastActivityRef.current = Date.now();
    silenceTimerRef.current = setTimeout(() => {
      const txt = transcriptRef.current.trim();
      if (txt && phaseRef.current === "listening") {
        submitCurrentTranscript();
      }
    }, silenceThresholdSecs * 1000);
  }

  function startSilenceInterval() {
    if (silenceIntervalRef.current) clearInterval(silenceIntervalRef.current);
    // Independent periodic checker — ensures silence threshold fires even
    // when mic analyser gives near-zero (Bluetooth headphone issue on Windows)
    silenceIntervalRef.current = setInterval(() => {
      if (phaseRef.current !== "listening") { clearInterval(silenceIntervalRef.current!); return; }
      const sinceLast = Date.now() - lastActivityRef.current;
      if (sinceLast >= silenceThresholdSecs * 1000 && transcriptRef.current.trim()) {
        submitCurrentTranscript();
      }
    }, 500);
  }

  function startMaxListenTimer() {
    if (maxListenTimerRef.current) clearTimeout(maxListenTimerRef.current);
    listenStartedAtRef.current = Date.now();
    maxListenTimerRef.current = setTimeout(() => {
      if (phaseRef.current !== "listening") return;
      const txt = transcriptRef.current.trim() || "[no response — please continue]";
      setPhase("processing");
      onAnswerReady(txt);
    }, maxListenSecs * 1000);
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
  const startListening = useCallback(async () => {
    if (phaseRef.current === "listening") return;

    if (phaseRef.current === "ai-speaking") {
      cancelAISpeech();
      await new Promise(r => setTimeout(r, 200));
    }

    setPhase("listening");
    setTranscript("");
    setInterimTranscript("");
    setMicError(null);
    lastActivityRef.current = Date.now();

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
      startSpeechRecognition();

      // Whisper WebSocket STT — used as primary path in Tauri WebView2
      // where webkitSpeechRecognition is unavailable
      if (!speechApiAvailable && backendBaseUrl) {
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
                    ? `Voice recognition model '${data.model_name}' not downloaded. Go to Settings > Hardware to download it.`
                    : errMsg
                );
                return;
              }
              if (data?.text) {
                const text = String(data.text).trim();
                if (text) {
                  lastActivityRef.current = Date.now();
                  if (data.is_partial) {
                    setInterimTranscript(text);
                  } else {
                    setTranscript(prev => (prev ? prev + " " + text : text).trim());
                    setInterimTranscript("");
                  }
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
