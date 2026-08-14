/**
 * VideoCallInterviewRoom — immersive video-call interview UI.
 *
 * Replaces the text-based InterviewRoom with a Google Meet–style layout:
 * - Large AI panel (avatar + speaking ring + waveform + question bubble)
 * - Small user webcam overlay (top-right)
 * - Transcript bar (live speech-to-text)
 * - Control bar (mic · cam · voice/text · code · end)
 * - Feedback toast after each answer
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useVoiceInterview } from "../../hooks/useVoiceInterview";

interface VideoCallInterviewRoomProps {
  currentMessage: string | null;
  lastFeedback: { score: number; feedback: string; reaction: string | null } | null;
  isComplete: boolean;
  busy: boolean;
  machineState: string;
  onSubmitWarmUp: (text: string) => void;
  onSubmitAnswer: (text: string) => void;
  onEnd: () => void;
  onBack: () => void;
  backendBaseUrl: string;
  personaName?: string;
  personaVoice?: string;
  enableCoding?: boolean;
  sessionId?: string | null;
}

// ── State helpers ──────────────────────────────────────────────────────────
// machineState can be:
//   "warmUp"                        → top-level state
//   '{"inProgress":"listening"}'    → nested state (XState serialization)
//   '{"inProgress":"asking"}'       → nested state
//   '{"inProgress":"followUp"}'     → nested state
//   "completed" / "archived"        → terminal

function isWarmUpState(s: string) { return s === "warmUp"; }

function isListeningPhase(s: string) {
  // Either top-level warmUp or any inProgress sub-state where user can answer
  return (
    isWarmUpState(s) ||
    s.includes('"listening"') ||
    s.includes('"followUp"') ||
    s.includes("listening") ||
    s.includes("followUp")
  );
}

function isActiveSession(s: string) {
  return (
    s === "warmUp" ||
    s.includes("inProgress") ||
    s.includes("listening") ||
    s.includes("asking") ||
    s.includes("followUp")
  );
}

// ── Score colour ───────────────────────────────────────────────────────────
function scoreColor(score: number) {
  if (score >= 0.8) return "var(--color-accent-success)";
  if (score >= 0.5) return "var(--color-accent-warning)";
  return "var(--color-accent-danger)";
}

// ── Sub-components ─────────────────────────────────────────────────────────

function Waveform({ level, active, color }: { level: number; active: boolean; color: string }) {
  const BAR_COUNT = 9;
  return (
    <div className="vcir__waveform" aria-hidden>
      {Array.from({ length: BAR_COUNT }, (_, i) => {
        const base = active ? Math.max(0.1, Math.min(1, level * (0.5 + Math.sin(i * 1.4) * 0.5))) : 0.08;
        return (
          <div
            key={i}
            className="vcir__waveform-bar"
            style={{
              "--bar-scale": base,
              "--bar-color": color,
              "--bar-delay": `${(i * 0.06).toFixed(2)}s`,
            } as React.CSSProperties}
          />
        );
      })}
    </div>
  );
}

function AIAvatar({ speaking, name }: { speaking: boolean; name: string }) {
  const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className={`vcir__ai-avatar${speaking ? " vcir__ai-avatar--speaking" : ""}`}>
      <div className="vcir__ai-avatar-ring" />
      <div className="vcir__ai-avatar-face">
        <div className="vcir__ai-avatar-icon">🤖</div>
        <span className="vcir__ai-avatar-initials">{initials}</span>
      </div>
    </div>
  );
}

function UserCamera({ active }: { active: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasStream, setHasStream] = useState(false);

  useEffect(() => {
    if (!active) { setHasStream(false); return; }
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: true, audio: false })
      .then(s => {
        stream = s;
        if (videoRef.current) { videoRef.current.srcObject = s; setHasStream(true); }
      })
      .catch(() => setHasStream(false));
    return () => {
      stream?.getTracks().forEach(t => t.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [active]);

  return (
    <div className="vcir__user-cam">
      {hasStream
        ? <video ref={videoRef} autoPlay muted playsInline className="vcir__user-video" />
        : (
          <div className="vcir__user-cam-placeholder">
            <span className="vcir__user-cam-icon">👤</span>
          </div>
        )
      }
      <div className="vcir__user-cam-badge">You</div>
    </div>
  );
}

function FeedbackToast({ feedback }: { feedback: { score: number; feedback: string; reaction: string | null } | null }) {
  if (!feedback) return null;
  const pct = Math.round(feedback.score * 100);
  return (
    <div className="vcir__feedback-toast">
      <div className="vcir__feedback-score" style={{ color: scoreColor(feedback.score) }}>{pct}%</div>
      <div className="vcir__feedback-body">
        {feedback.reaction && <em className="vcir__feedback-reaction">{feedback.reaction}</em>}
        <p className="vcir__feedback-text">{feedback.feedback}</p>
      </div>
    </div>
  );
}

function PhasePill({ phase, machineState }: { phase: string; machineState: string }) {
  const phaseLabels: Record<string, string> = {
    idle: "Standby",
    "ai-speaking": "AI Speaking…",
    listening: "Listening…",
    processing: "Processing…",
    paused: "Paused",
  };
  const stateLabel = isWarmUpState(machineState) ? "Warm-Up"
    : machineState.includes("listening") ? "Interview Q&A"
    : machineState.includes("followUp") ? "Follow-Up"
    : machineState.includes("asking") ? "Next Question"
    : machineState.includes("completed") ? "Complete"
    : "Interview";

  return (
    <div className="vcir__phase-pill">
      <span className={`vcir__phase-dot vcir__phase-dot--${phase}`} />
      <span>{phaseLabels[phase] ?? phase}</span>
      <span className="vcir__phase-divider">·</span>
      <span className="vcir__phase-state">{stateLabel}</span>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function VideoCallInterviewRoom({
  currentMessage,
  lastFeedback,
  isComplete,
  busy,
  machineState,
  onSubmitWarmUp,
  onSubmitAnswer,
  onEnd,
  onBack,
  backendBaseUrl,
  personaName = "AI Interviewer",
  personaVoice = "en-US-AvaNeural",
  enableCoding = false,
}: VideoCallInterviewRoomProps) {
  const isWarmUp = isWarmUpState(machineState);
  const canUserAnswer = isListeningPhase(machineState);

  // ── Stable refs so callbacks don't go stale ────────────────────────────
  const phaseRef = useRef("idle");
  const machineStateRef = useRef(machineState);
  const canUserAnswerRef = useRef(canUserAnswer);
  useEffect(() => { machineStateRef.current = machineState; }, [machineState]);
  useEffect(() => { canUserAnswerRef.current = canUserAnswer; }, [canUserAnswer]);

  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [camEnabled, setCamEnabled] = useState(true);
  const [manualAnswer, setManualAnswer] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const [lastPlayedMessage, setLastPlayedMessage] = useState<string | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [timerSecs, setTimerSecs] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Answer submission — reads machineState via ref (no stale closure) ──
  const handleAnswerReady = useCallback(
    (text: string) => {
      voice.stopListening();
      voice.clearTranscript();
      if (isWarmUpState(machineStateRef.current)) {
        onSubmitWarmUp(text);
      } else {
        onSubmitAnswer(text);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onSubmitWarmUp, onSubmitAnswer]
  );

  const voice = useVoiceInterview({
    backendBaseUrl,
    onAnswerReady: handleAnswerReady,
    silenceThresholdSecs: 2.5,
    enabled: voiceEnabled,
  });

  // Keep phaseRef in sync
  useEffect(() => { phaseRef.current = voice.phase; }, [voice.phase]);

  // ── Speak AI message when it changes ──────────────────────────────────
  useEffect(() => {
    if (!currentMessage || currentMessage === lastPlayedMessage) return;
    // Speak for warmUp, inProgress, or any active session state
    if (!isActiveSession(machineState) && !isWarmUpState(machineState)) return;

    setLastPlayedMessage(currentMessage);
    setShowFeedback(false);

    if (!voiceEnabled) return; // text-only mode — just show the text

    voice.stopListening();

    // Short delay so React state has settled
    const t = setTimeout(async () => {
      await voice.speakAsAI(currentMessage, personaVoice);
      // After AI finishes speaking, start listening if it's the user's turn
      if (phaseRef.current !== "processing" && canUserAnswerRef.current) {
        voice.clearTranscript();
        voice.startListening();
      }
    }, 300);

    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentMessage, machineState, voiceEnabled]);

  // ── Feedback toast ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!lastFeedback) return;
    setShowFeedback(true);
    const t = setTimeout(() => setShowFeedback(false), 6000);
    return () => clearTimeout(t);
  }, [lastFeedback]);

  // ── Interview timer ────────────────────────────────────────────────────
  useEffect(() => {
    if (!isComplete) {
      timerRef.current = setInterval(() => setTimerSecs(s => s + 1), 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isComplete]);

  function formatTime(s: number) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }

  // Auto-show text input box if Speech API is unavailable in this environment (e.g. WebView2)
  useEffect(() => {
    if (!voice.speechApiAvailable) {
      setShowManualInput(true);
    }
  }, [voice.speechApiAvailable]);

  // ── Mic toggle ─────────────────────────────────────────────────────────
  function handleMicToggle() {
    if (!voice.speechApiAvailable) {
      setShowManualInput(true);
    }
    if (voice.phase === "listening") {
      voice.stopListening();
    } else {
      voice.clearTranscript();
      voice.startListening();
    }
  }

  // ── Manual text send ───────────────────────────────────────────────────
  function handleManualSend() {
    if (!manualAnswer.trim() || busy) return;
    voice.stopListening();
    handleAnswerReady(manualAnswer);
    setManualAnswer("");
    if (voice.speechApiAvailable) {
      setShowManualInput(false);
    }
  }

  // ── Complete screen ────────────────────────────────────────────────────
  if (isComplete) {
    return (
      <div className="vcir vcir--complete">
        <div className="vcir__complete-card">
          <div className="vcir__complete-icon">🎉</div>
          <h2 className="vcir__complete-title">Interview Complete!</h2>
          <p className="vcir__complete-body">
            Excellent work! Your answers have been recorded and evaluated.
            Check the <strong>Session Report</strong> for your detailed scoring breakdown.
          </p>
          <div className="vcir__complete-time">Session time: {formatTime(timerSecs)}</div>
          <div className="vcir__complete-actions">
            <button
              id="vcir-back-btn"
              className="vcir__complete-back-btn"
              onClick={onBack}
              type="button"
            >
              ← Back to Setup
            </button>
          </div>
        </div>
      </div>
    );
  }

  const displayTranscript = voice.transcript + (voice.interimTranscript ? " " + voice.interimTranscript : "");

  return (
    <div className="vcir">
      {/* ── Top bar ── */}
      <div className="vcir__top-bar">
        <div className="vcir__top-brand">
          <span className="vcir__top-brand-mark">P</span>
          <span>Poise Interview</span>
        </div>
        <PhasePill phase={voice.phase} machineState={machineState} />
        <div className="vcir__timer">{formatTime(timerSecs)}</div>
      </div>

      {/* ── Main stage ── */}
      <div className="vcir__stage">
        {/* AI panel */}
        <div className="vcir__ai-panel">
          <div className="vcir__ai-panel-inner">
            <AIAvatar speaking={voice.isAISpeaking} name={personaName} />
            <div className="vcir__ai-name">{personaName}</div>
            <Waveform level={voice.aiAudioLevel} active={voice.isAISpeaking} color="var(--color-accent-primary)" />
            {currentMessage && (
              <div className="vcir__ai-speech-bubble">
                <p>{currentMessage}</p>
              </div>
            )}
          </div>
        </div>

        {/* User panel */}
        <div className="vcir__user-panel">
          <UserCamera active={camEnabled} />
          {voice.phase === "listening" && (
            <div className="vcir__user-waveform">
              <Waveform level={voice.vadLevel} active={voice.isSpeaking} color="var(--color-accent-secondary)" />
            </div>
          )}
        </div>
      </div>

      {/* ── Mic error banner ── */}
      {voice.micError && (
        <div className="vcir__mic-error-banner" role="alert">
          <div className="vcir__mic-error-header">🎙️ Microphone issue detected</div>
          <pre className="vcir__mic-error-body">{voice.micError}</pre>
          <div className="vcir__mic-error-actions">
            <button
              className="vcir__mic-error-retry"
              onClick={() => { voice.clearTranscript(); voice.startListening(); }}
            >
              🔄 Retry Microphone
            </button>
            <button
              className="vcir__mic-error-text"
              onClick={() => setShowManualInput(true)}
            >
              💬 Type Instead
            </button>
          </div>
        </div>
      )}

      {/* ── Transcript bar ── */}
      {voice.phase === "listening" && (
        <div className="vcir__transcript-area">
          <div className="vcir__transcript-label">
            <span className={`vcir__transcript-dot${voice.isSpeaking ? " vcir__transcript-dot--active" : ""}`} />
            {voice.isSpeaking ? "Speaking… (stop for 2.5 s to auto-submit)" : voice.transcript ? "Pause detected — will submit shortly" : "Listening for your answer…"}
          </div>
          {displayTranscript && (
            <div className="vcir__transcript-text">
              <span className="vcir__transcript-final">{voice.transcript}</span>
              {voice.interimTranscript && (
                <span className="vcir__transcript-interim"> {voice.interimTranscript}</span>
              )}
            </div>
          )}
          {!voice.speechApiAvailable && (
            <p className="vcir__transcript-hint" style={{ color: "var(--color-accent-info, #60a5fa)" }}>
              🎤 Whisper STT active (Bluetooth/headphone mode). Auto-submits after 2.5 s pause, or 45 s max.
            </p>
          )}
          <p className="vcir__transcript-hint">
            <button className="vcir__transcript-manual-btn" onClick={() => setShowManualInput(v => !v)}>
              {showManualInput ? "Hide text input" : "Type your answer instead"}
            </button>
          </p>
        </div>
      )}

      {/* ── Manual text input ── */}
      {(showManualInput || !voiceEnabled) && (
        <div className="vcir__manual-input-area">
          <textarea
            className="vcir__manual-textarea"
            value={manualAnswer}
            onChange={e => setManualAnswer(e.target.value)}
            placeholder={isWarmUp ? "Type your reply…" : "Type your answer…"}
            rows={3}
            onKeyDown={e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleManualSend(); }}
          />
          <div className="vcir__manual-send-row">
            <span className="vcir__manual-hint">Ctrl+Enter to send</span>
            <button
              className="vcir__manual-send-btn"
              onClick={handleManualSend}
              disabled={!manualAnswer.trim() || busy}
            >
              {busy ? "Sending…" : "Send ↩"}
            </button>
          </div>
        </div>
      )}

      {/* ── Feedback toast ── */}
      {showFeedback && lastFeedback && <FeedbackToast feedback={lastFeedback} />}

      {/* ── Bottom control bar ── */}
      <div className="vcir__bottom-bar">
        {/* Mic */}
        <button
          id="vcir-mic-btn"
          className={`vcir__ctrl-btn${voice.phase === "listening" ? " vcir__ctrl-btn--active" : ""}`}
          onClick={handleMicToggle}
          title={voice.phase === "listening" ? "Stop microphone" : "Start microphone"}
          aria-label={voice.phase === "listening" ? "Stop microphone" : "Start microphone"}
        >
          <span className="vcir__ctrl-icon">{voice.phase === "listening" ? "🎙️" : "🎤"}</span>
          <span className="vcir__ctrl-label">{voice.phase === "listening" ? "Mic On" : "Mic Off"}</span>
        </button>

        {/* Camera */}
        <button
          id="vcir-cam-btn"
          className={`vcir__ctrl-btn${camEnabled ? " vcir__ctrl-btn--active" : ""}`}
          onClick={() => setCamEnabled(v => !v)}
          title={camEnabled ? "Turn off camera" : "Turn on camera"}
          aria-label={camEnabled ? "Turn off camera" : "Turn on camera"}
        >
          <span className="vcir__ctrl-icon">{camEnabled ? "📷" : "🚫"}</span>
          <span className="vcir__ctrl-label">{camEnabled ? "Cam On" : "Cam Off"}</span>
        </button>

        {/* Voice/Text toggle */}
        <button
          id="vcir-voice-btn"
          className={`vcir__ctrl-btn${voiceEnabled ? " vcir__ctrl-btn--active" : ""}`}
          onClick={() => {
            const next = !voiceEnabled;
            setVoiceEnabled(next);
            if (!next) {
              voice.cancelAISpeech();
              voice.stopListening();
            }
            setShowManualInput(!next);
          }}
          title={voiceEnabled ? "Switch to text mode" : "Switch to voice mode"}
          aria-label={voiceEnabled ? "Disable voice" : "Enable voice"}
        >
          <span className="vcir__ctrl-icon">{voiceEnabled ? "🔊" : "💬"}</span>
          <span className="vcir__ctrl-label">{voiceEnabled ? "Voice" : "Text"}</span>
        </button>

        {/* Coding sandbox */}
        {enableCoding && (
          <button
            id="vcir-code-btn"
            className="vcir__ctrl-btn"
            onClick={() => window.dispatchEvent(new CustomEvent("poise:open-coding"))}
            title="Open coding sandbox"
            aria-label="Open coding sandbox"
          >
            <span className="vcir__ctrl-icon">💻</span>
            <span className="vcir__ctrl-label">Code</span>
          </button>
        )}

        <div className="vcir__bottom-spacer" />

        {/* End interview — NEVER disabled by busy; always escapable */}
        <button
          id="vcir-end-btn"
          className="vcir__ctrl-btn vcir__ctrl-btn--danger"
          onClick={() => {
            voice.cancelAISpeech();
            voice.stopListening();
            onEnd();
          }}
          title="End interview"
          aria-label="End interview"
        >
          <span className="vcir__ctrl-icon">📵</span>
          <span className="vcir__ctrl-label">End</span>
        </button>
      </div>

      {/* ── Processing overlay (lighter — doesn't block End) ── */}
      {busy && voice.phase === "processing" && (
        <div className="vcir__loading-overlay" aria-live="polite">
          <div className="vcir__loading-spinner" />
          <span>AI is evaluating…</span>
        </div>
      )}
    </div>
  );
}
