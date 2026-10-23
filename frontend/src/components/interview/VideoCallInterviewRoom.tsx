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
import { CodingRound } from "../../pages/CodingRound";
import { CodingAPI } from "../../lib/codingApi";
import { api as sharedApi } from "../../lib/api";
import { cleanSpeechText, unlockGlobalAudio } from "../../lib/audio-manager";

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
  onViewReport?: () => void;
  backendBaseUrl: string;
  personaName?: string;
  personaVoice?: string;
  enableCoding?: boolean;
  sessionId?: string | null;
  error?: string | null;
}

// ── State helpers ──────────────────────────────────────────────────────────
// machineState can be:
//   "warmUp"                        → top-level state
//   '{"inProgress":"listening"}'    → nested state (XState serialization)
//   '{"inProgress":"asking"}'       → nested state
//   '{"inProgress":"followUp"}'     → nested state
//   "completed" / "archived"        → terminal

function isWarmUpState(s: string) { return s === "warmUp"; }

function isCodingQuestionText(text?: string | null): boolean {
  if (!text) return false;
  const lower = text.toLowerCase();
  const triggers = [
    "write code",
    "design a simple api",
    "design an api",
    "design a rest api",
    "implement a",
    "implement the",
    "implement an",
    "write a function",
    "write a program",
    "write a script",
    "write a query",
    "write sql",
    "write the code",
    "create an api",
    "create a class",
    "create a function",
    "create an endpoint",
    "using django",
    "using flask",
    "using fastapi",
    "using express",
    "using spring",
    "in python",
    "in javascript",
    "in typescript",
    "in java",
    "in c++",
    "in sql",
    "code that",
    "coding challenge",
    "live coding",
  ];
  return triggers.some((t) => lower.includes(t));
}

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
    const videoEl = videoRef.current;
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
      if (videoEl) videoEl.srcObject = null;
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

function FeedbackToast({
  feedback,
  onClose,
}: {
  feedback: { score: number; feedback: string; reaction: string | null } | null;
  onClose?: () => void;
}) {
  if (!feedback) return null;
  const pct = Math.round(feedback.score * 100);
  return (
    <div className="vcir__feedback-toast" role="status" aria-live="polite">
      <div className="vcir__feedback-score" style={{ color: scoreColor(feedback.score) }}>{pct}%</div>
      <div className="vcir__feedback-body">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", gap: "8px" }}>
          {feedback.reaction ? (
            <em className="vcir__feedback-reaction">{feedback.reaction}</em>
          ) : (
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-secondary, #94a3b8)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Feedback</span>
          )}
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--color-text-secondary, #94a3b8)",
                cursor: "pointer",
                padding: "0 4px",
                fontSize: "0.85rem",
                lineHeight: 1,
              }}
              title="Dismiss"
              aria-label="Dismiss feedback"
            >
              ✕
            </button>
          )}
        </div>
        <p className="vcir__feedback-text">{feedback.feedback}</p>
      </div>
    </div>
  );
}

function PhasePill({
  phase,
  machineState,
  evaluating,
}: {
  phase: string;
  machineState: string;
  evaluating?: boolean;
}) {
  const phaseLabels: Record<string, string> = {
    idle: "Standby",
    "ai-speaking": "Interviewer Speaking",
    listening: "Listening for Answer…",
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
      <span>{evaluating ? "Evaluating in background…" : (phaseLabels[phase] ?? phase)}</span>
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
  onViewReport,
  backendBaseUrl,
  personaName = "AI Interviewer",
  personaVoice = "en-US-AvaNeural",
  enableCoding: _enableCoding = false,
  sessionId,
  error,
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
  const playedMessageRef = useRef<string | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [timerSecs, setTimerSecs] = useState(0);
  const [showCoding, setShowCoding] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const handler = () => setShowCoding(true);
    window.addEventListener("poise:open-coding", handler);
    return () => window.removeEventListener("poise:open-coding", handler);
  }, []);

  // ── Auto-detect coding questions and open the live coding sandbox automatically ──
  useEffect(() => {
    if (currentMessage && isCodingQuestionText(currentMessage)) {
      setShowCoding(true);
    }
  }, [currentMessage]);

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

  // Prime audio hardware on room mount
  useEffect(() => {
    unlockGlobalAudio();
  }, []);

  // ── Auto-play AI message immediately when it changes ──────────────────
  useEffect(() => {
    if (!currentMessage || !currentMessage.trim() || isComplete) return;
    if (currentMessage === playedMessageRef.current) return;

    playedMessageRef.current = currentMessage;
    setShowFeedback(false);

    if (!voiceEnabled) return;

    voice.stopListening();

    let cancelled = false;

    // Clean markdown formatting before speaking so the voice sounds natural and conversational
    const speechText = cleanSpeechText(currentMessage);

    // Immediately trigger speakAsAI so the voice auto-plays right as the question appears
    voice.speakAsAI(speechText, personaVoice).then(() => {
      if (!cancelled && canUserAnswerRef.current) {
        voice.clearTranscript();
        voice.startListening();
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentMessage, voiceEnabled]);

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
          <div className="vcir__complete-actions" style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
            {onViewReport && (
              <button
                id="vcir-report-btn"
                className="vcir__complete-back-btn"
                style={{ background: "var(--color-accent-primary, #6366f1)", color: "#fff", border: "none" }}
                onClick={onViewReport}
                type="button"
              >
                📊 View Scoring Report →
              </button>
            )}
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
    <div className={`vcir${showCoding ? " vcir--with-coding" : ""}`} onPointerDown={unlockGlobalAudio}>
      {/* ── Top bar ── */}
      <div className="vcir__top-bar">
        <div className="vcir__top-brand">
          <span className="vcir__top-brand-mark">P</span>
          <span>Poise Interview</span>
        </div>
        <PhasePill phase={voice.phase} machineState={machineState} evaluating={busy} />
        <div className="vcir__timer">{formatTime(timerSecs)}</div>
      </div>

      {/* ── Main content (Split-screen when coding is active) ── */}
      <div className="vcir__main-container">
        {/* Left / Primary Stage Pane */}
        <div className="vcir__stage-pane">
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
                    <div style={{ marginTop: "10px", display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                      <button
                        type="button"
                        id="vcir-replay-question-btn"
                        style={{
                          background: voice.isAISpeaking ? "rgba(99, 102, 241, 0.4)" : "rgba(255, 255, 255, 0.08)",
                          border: "1px solid rgba(255, 255, 255, 0.2)",
                          color: "#e2e8f0",
                          padding: "4px 12px",
                          borderRadius: "14px",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                        onClick={() => {
                          unlockGlobalAudio();
                          const speechText = cleanSpeechText(currentMessage);
                          voice.speakAsAI(speechText, personaVoice);
                        }}
                        title="Replay this question aloud"
                      >
                        {voice.isAISpeaking ? "🔊 Speaking…" : "🔊 Replay Question"}
                      </button>
                      {isWarmUp && (
                        <button
                          type="button"
                          id="vcir-skip-warmup-btn"
                          style={{
                            background: "rgba(99, 102, 241, 0.25)",
                            border: "1px solid rgba(99, 102, 241, 0.5)",
                            color: "#c7d2fe",
                            padding: "4px 12px",
                            borderRadius: "14px",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                          }}
                          onClick={() => {
                            voice.stopListening();
                            onSubmitWarmUp("Ready to begin the interview.");
                          }}
                          title="Skip introduction and start interview questions directly"
                        >
                          ⏩ Start Interview Questions
                        </button>
                      )}
                    </div>
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

          {/* ── Error banner ── */}
          {error && (
            <div className="vcir__mic-error-banner" role="alert" style={{ borderColor: "var(--color-accent-danger, #ef4444)" }}>
              <div className="vcir__mic-error-header" style={{ color: "var(--color-accent-danger, #ef4444)" }}>
                ⚠️ Notice
              </div>
              <pre className="vcir__mic-error-body">{error}</pre>
            </div>
          )}

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
                  disabled={!manualAnswer.trim()}
                >
                  Send ↩
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right / Live Coding Pane (Split-Screen) */}
        {showCoding && (
          <div className="vcir__coding-pane">
            <div className="vcir__coding-pane-header">
              <span className="vcir__coding-pane-title">
                💻 <span>Live Coding Environment</span>
              </span>
              <button
                className="vcir__ctrl-btn"
                onClick={() => setShowCoding(false)}
                style={{ padding: "4px 12px", fontSize: "0.8rem", minWidth: "unset" }}
                title="Hide coding panel"
              >
                ✕ Hide
              </button>
            </div>
            <div className="vcir__coding-pane-body">
              <CodingRound
                sessionId={sessionId ?? "demo-session"}
                codingApi={new CodingAPI(sharedApi)}
                questionPrompt={currentMessage ?? undefined}
                personaId={personaName ? personaName.toLowerCase() : "professional"}
                onInterimReview={(interviewerMessage) => {
                  if (voiceEnabled) {
                    voice.speakAsAI(interviewerMessage, personaVoice);
                  }
                }}
                onComplete={(_eval, codeSubmitted) => {
                  if (codeSubmitted) {
                    const answer = `Here is my code solution:\n\n\`\`\`\n${codeSubmitted}\n\`\`\``;
                    handleAnswerReady(answer);
                  }
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Feedback toast ── */}
      {showFeedback && lastFeedback && (
        <FeedbackToast feedback={lastFeedback} onClose={() => setShowFeedback(false)} />
      )}

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

        {/* Coding toggle */}
        <button
          id="vcir-code-btn"
          className={`vcir__ctrl-btn${showCoding ? " vcir__ctrl-btn--active" : ""}`}
          onClick={() => setShowCoding((v) => !v)}
          title={showCoding ? "Hide coding sandbox" : "Open coding sandbox"}
          aria-label="Toggle coding sandbox"
        >
          <span className="vcir__ctrl-icon">💻</span>
          <span className="vcir__ctrl-label">{showCoding ? "Hide Code" : "Code"}</span>
        </button>

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
