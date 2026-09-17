import { AnimatePresence, motion } from "framer-motion";
import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { CueCard } from "../components/ielts/CueCard";
import { PartIndicator } from "../components/ielts/PartIndicator";
import { PrepTimer } from "../components/ielts/PrepTimer";
import { ScoreReveal } from "../components/ielts/ScoreReveal";
import { useIELTSSession } from "../hooks/useIELTSSession";
import { useVoiceInterview } from "../hooks/useVoiceInterview";
import type { PoiseAPI } from "../lib/api";
import "../styles/ielts.css";

const FADE_TRANSITION = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
  transition: { duration: 0.25, ease: [0.4, 0, 0.2, 1] },
};

const BAND_DESCRIPTORS: Record<number, { title: string; desc: string }> = {
  5.0: { title: "Modest User", desc: "Partial command of the language, coping with overall meaning in most situations." },
  5.5: { title: "Modest / Competent", desc: "Borderline competent with occasional inaccuracies and misunderstandings." },
  6.0: { title: "Competent User", desc: "Generally effective command of language despite some inaccuracies and inappropriate usage." },
  6.5: { title: "Competent / Good", desc: "Solid grasp of complex language with generally good fluency and coherence." },
  7.0: { title: "Good User", desc: "Operational command of the language with occasional inaccuracies and misunderstandings in some situations." },
  7.5: { title: "Good / Very Good", desc: "Handles complex language well and understands detailed reasoning with minor hesitations." },
  8.0: { title: "Very Good User", desc: "Fully operational command of the language with only occasional unsystematic inaccuracies." },
  8.5: { title: "Very Good / Expert", desc: "Approaching native fluency with sophisticated vocabulary and natural prosody." },
  9.0: { title: "Expert User", desc: "Complete operational command: appropriate, accurate, and fluent with complete understanding." },
};

const BAND_OPTIONS = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0];

interface IELTSSessionProps {
  api: PoiseAPI | null;
}

export default function IELTSSession({ api }: IELTSSessionProps) {
  const navigate = useNavigate();
  const {
    state,
    send,
    prompt,
    score,
    error,
    sessionId,
    parentSessionId,
    prepRemaining,
    speakingRemaining,
    isBusy,
  } = useIELTSSession(api);

  const [targetBand, setTargetBand] = useState<number>(6.5);
  const [manualAnswer, setManualAnswer] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const lastPlayedRef = useRef<string | null>(null);

  const handleAnswerReady = useCallback(
    (text: string) => {
      send({
        type: "ANSWER_SUBMITTED",
        audioPath: "/tmp/dummy.wav",
        transcript: text,
      });
    },
    [send]
  );

  const backendBaseUrl = api?.baseUrlValue || "http://127.0.0.1:8000";

  const voice = useVoiceInterview({
    backendBaseUrl,
    onAnswerReady: handleAnswerReady,
  });

  // ── Voice TTS & Auto-Listen Routing ──────────────────────────────────────
  useEffect(() => {
    if (!prompt && !state.matches("part1Intro")) return;

    let messageToSpeak: string | null = null;
    let shouldListenAfter = false;

    if (state.matches("part1Intro")) {
      messageToSpeak = "Let's begin with some questions about yourself.";
    } else if (state.matches("part1QA")) {
      messageToSpeak = prompt?.question || null;
      shouldListenAfter = true;
    } else if (state.matches("part2CueCard")) {
      messageToSpeak = "Here is your topic. You will have one minute to prepare.";
    } else if (state.matches("part2Speaking")) {
      messageToSpeak = "You may start speaking now.";
      shouldListenAfter = true;
    } else if (state.matches("part2FollowUp")) {
      messageToSpeak = prompt?.question || "Now, let's talk about the topic a little more generally.";
      shouldListenAfter = true;
    } else if (state.matches("part3Discussion")) {
      messageToSpeak = prompt?.question || null;
      shouldListenAfter = true;
    }

    if (messageToSpeak && messageToSpeak !== lastPlayedRef.current) {
      lastPlayedRef.current = messageToSpeak;

      voice.stopListening();
      voice.speakAsAI(messageToSpeak).then(() => {
        if (shouldListenAfter && !state.matches("error") && !state.matches("complete")) {
          voice.clearTranscript();
          voice.startListening();
        }
      });
    }
  }, [state.value, prompt, voice, state]);

  const handleManualSend = () => {
    if (!manualAnswer.trim() || isBusy) return;
    voice.stopListening();
    handleAnswerReady(manualAnswer);
    setManualAnswer("");
  };

  const descriptor = BAND_DESCRIPTORS[targetBand] ?? BAND_DESCRIPTORS[6.5];

  // ── Render Response & Voice Controller ──────────────────────────────────
  const renderVoiceController = () => {
    const isAiSpeaking = voice.phase === "ai-speaking";
    const isListening = voice.phase === "listening";

    return (
      <div className="ielts-voice-workspace">
        <div className="ielts-voice-status">
          <span
            className={`ielts-voice-pulse ${
              isAiSpeaking
                ? "ielts-voice-pulse--ai"
                : isListening && voice.isSpeaking
                ? "ielts-voice-pulse--speaking"
                : isListening
                ? "ielts-voice-pulse--listening"
                : ""
            }`}
          />
          <span>
            {isAiSpeaking
              ? "Examiner is speaking…"
              : isListening && voice.isSpeaking
              ? "Speaking detected (pause to submit)"
              : isListening && voice.transcript
              ? "Pause detected — submitting response shortly"
              : isListening
              ? "Listening for your response…"
              : "Microphone idle"}
          </span>
        </div>

        {/* Live Audio Transcript Display */}
        <div className="ielts-transcript-display">
          {(voice.transcript || voice.interimTranscript) ? (
            <>
              {voice.transcript && <span>{voice.transcript}</span>}
              {voice.interimTranscript && (
                <span className="ielts-transcript-interim"> {voice.interimTranscript}</span>
              )}
            </>
          ) : isListening ? (
            <span style={{ color: "var(--color-text-muted)" }}>
              Speak naturally into your microphone…
            </span>
          ) : null}
        </div>

        {/* Control Action Buttons */}
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", justifyContent: "center" }}>
          {!isBusy && !isAiSpeaking && !isListening && (
            <button
              type="button"
              className="ielts-primary-btn"
              onClick={() => {
                voice.clearTranscript();
                voice.startListening();
              }}
            >
              🎙️ Start Microphone
            </button>
          )}

          {isListening && (
            <button
              type="button"
              className="ielts-secondary-btn"
              onClick={() => {
                const textToSubmit = (voice.transcript + " " + (voice.interimTranscript || "")).trim();
                if (textToSubmit) {
                  handleAnswerReady(textToSubmit);
                  voice.clearTranscript();
                }
                voice.stopListening();
              }}
            >
              ✓ Finish Speaking
            </button>
          )}

          <button
            type="button"
            className="ielts-secondary-btn"
            onClick={() => setShowManualInput((v) => !v)}
          >
            {showManualInput ? "⌨️ Hide Text Input" : "⌨️ Type Instead"}
          </button>
        </div>

        {/* Manual Keyboard Input Fallback */}
        {showManualInput && (
          <div className="ielts-manual-box">
            <textarea
              className="ielts-manual-textarea"
              value={manualAnswer}
              onChange={(e) => setManualAnswer(e.target.value)}
              placeholder="Type your spoken response here…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleManualSend();
              }}
            />
            <div className="ielts-manual-footer">
              <span>Press Ctrl + Enter to submit</span>
              <button
                type="button"
                className="ielts-primary-btn"
                onClick={handleManualSend}
                disabled={isBusy || !manualAnswer.trim()}
                style={{ padding: "var(--space-2) var(--space-4)", fontSize: "0.85rem" }}
              >
                Submit Response
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ── View: Disconnected / Sidecar Missing ─────────────────────────────────
  if (!api) {
    return (
      <div className="ielts-container">
        <div className="ielts-header">
          <h1 className="ielts-header__title">IELTS Speaking Practice</h1>
          <p className="ielts-header__subtitle">
            Official format Parts 1, 2, and 3 simulation evaluated across Fluency, Lexical Resource,
            Grammar, and Pronunciation.
          </p>
        </div>

        <div className="ielts-card" style={{ borderColor: "var(--color-accent-warning)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <span style={{ fontSize: "1.5rem" }}>⚠️</span>
            <div>
              <h3 style={{ margin: 0, color: "var(--color-text-primary)" }}>
                Backend Sidecar Not Connected
              </h3>
              <p style={{ margin: "var(--space-1) 0 0", color: "var(--color-text-secondary)", fontSize: "0.9rem" }}>
                Please wait a moment while the local AI backend initialises, or check the status bar below.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── View: Error State ───────────────────────────────────────────────────
  if (state.matches("error")) {
    return (
      <div className="ielts-container">
        <div className="ielts-header">
          <h1 className="ielts-header__title">IELTS Speaking Practice</h1>
        </div>

        <div className="ielts-card" style={{ borderColor: "var(--color-accent-danger)" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", alignItems: "flex-start" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
              <span style={{ fontSize: "1.5rem" }}>❌</span>
              <div>
                <h3 style={{ margin: 0, color: "var(--color-text-primary)" }}>Session Encountered an Error</h3>
                <p style={{ margin: "var(--space-1) 0 0", color: "var(--color-accent-danger)", fontSize: "0.9rem" }}>
                  {error || "An unexpected error occurred during the session."}
                </p>
              </div>
            </div>
            <button
              type="button"
              className="ielts-primary-btn"
              onClick={() => send({ type: "RETRY" })}
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── View: Idle / Setup Screen ───────────────────────────────────────────
  if (state.matches("idle")) {
    return (
      <div className="ielts-container">
        <div className="ielts-header">
          <div className="ielts-header__title-row">
            <h1 className="ielts-header__title">
              IELTS Speaking Practice
              <span className="ielts-header__badge">Interactive Simulator</span>
            </h1>
          </div>
          <p className="ielts-header__subtitle">
            Complete a full 11–14 minute IELTS Speaking exam with an AI examiner. Practice Part 1
            introduction questions, Part 2 long turns with timed preparation, and Part 3 abstract
            discussion.
          </p>
        </div>

        {/* 3-Part Overview Cards */}
        <div className="ielts-grid-3">
          <div className="ielts-part-card">
            <span className="ielts-part-card__tag">Part 1 · 4–5 Mins</span>
            <h3 className="ielts-part-card__title">Introduction & Interview</h3>
            <p className="ielts-part-card__detail">
              Warm-up questions on familiar topics like work, studies, hobbies, hometown, and daily routine.
            </p>
          </div>

          <div className="ielts-part-card">
            <span className="ielts-part-card__tag">Part 2 · 3–4 Mins</span>
            <h3 className="ielts-part-card__title">Individual Long Turn</h3>
            <p className="ielts-part-card__detail">
              Receive a cue card with bullet prompts. 1 minute to plan notes followed by 1–2 minutes speaking.
            </p>
          </div>

          <div className="ielts-part-card">
            <span className="ielts-part-card__tag">Part 3 · 4–5 Mins</span>
            <h3 className="ielts-part-card__title">Two-Way Discussion</h3>
            <p className="ielts-part-card__detail">
              Deeper discussion on abstract themes, expressing opinions, analyzing trends, and speculating.
            </p>
          </div>
        </div>

        {/* Configuration Card */}
        <div className="ielts-card">
          <div className="ielts-card__header">
            <div className="ielts-card__step">01</div>
            <div>
              <h2 className="ielts-card__title">Target Band Score</h2>
              <p className="ielts-card__desc">
                Select your target band to tailor examiner rigor and benchmark feedback.
              </p>
            </div>
          </div>

          <div className="ielts-band-selector">
            <div className="ielts-band-pills">
              {BAND_OPTIONS.map((b) => (
                <button
                  key={b}
                  type="button"
                  className={`ielts-band-pill ${targetBand === b ? "ielts-band-pill--active" : ""}`}
                  onClick={() => setTargetBand(b)}
                >
                  Band {b.toFixed(1)}
                </button>
              ))}
            </div>

            <div className="ielts-band-helper">
              <span>🎯</span>
              <div>
                <strong>Band {targetBand.toFixed(1)} — {descriptor.title}:</strong> {descriptor.desc}
              </div>
            </div>
          </div>
        </div>

        {/* Readiness Card & Launch */}
        <div className="ielts-card">
          <div className="ielts-card__header">
            <div className="ielts-card__step">02</div>
            <div>
              <h2 className="ielts-card__title">Audio & Environment Check</h2>
              <p className="ielts-card__desc">
                Ensure your microphone is connected and you are in a quiet practice setting.
              </p>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", color: "var(--color-text-secondary)", fontSize: "0.9rem" }}>
              <span style={{ color: "var(--color-accent-success)" }}>●</span> Voice pipeline ready with real-time VAD silence detection
            </div>

            <button
              type="button"
              className="ielts-primary-btn"
              onClick={() => send({ type: "CREATE", targetBand })}
              disabled={isBusy}
              style={{ minWidth: "220px" }}
            >
              {isBusy ? "Configuring Session…" : "Start IELTS Simulation →"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── View: Creating Session ───────────────────────────────────────────────
  if (state.matches("creating")) {
    return (
      <div className="ielts-container">
        <div className="ielts-stage-card">
          <div className="ielts-stage-badge ielts-stage-badge--active">Preparing Simulation</div>
          <h2 className="ielts-stage-question">Generating Authentic IELTS Prompts…</h2>
          <p className="ielts-stage-hint">
            The AI examiner is synthesizing personalized question sets for Parts 1, 2, and 3 tailored to
            your Band {targetBand.toFixed(1)} target.
          </p>
        </div>
      </div>
    );
  }

  // ── View: Ready to Start ─────────────────────────────────────────────────
  if (state.matches("readyToStart")) {
    return (
      <div className="ielts-container">
        <div className="ielts-stage-card">
          <div className="ielts-stage-badge ielts-stage-badge--active">Session Ready</div>
          <h2 className="ielts-stage-question">Ready When You Are</h2>
          <p className="ielts-stage-hint">
            The examiner will greet you and guide you through each section. Speak clearly at a natural pace.
          </p>
          <button
            type="button"
            className="ielts-primary-btn"
            onClick={() => send({ type: "BEGIN" })}
            disabled={isBusy}
            style={{ minWidth: "200px" }}
          >
            {isBusy ? "Starting…" : "Begin Test Now →"}
          </button>
        </div>
      </div>
    );
  }

  // ── View: Complete / Score Reveal ────────────────────────────────────────
  if (state.matches("complete") && score) {
    return (
      <div className="ielts-container">
        <div className="ielts-header">
          <div className="ielts-header__title-row">
            <h1 className="ielts-header__title">IELTS Speaking Assessment</h1>
            <span className="ielts-header__badge">Official 4-Criteria Assessment</span>
          </div>
          <p className="ielts-header__subtitle">
            Performance scored holistically against Fluency &amp; Coherence, Lexical Resource,
            Grammatical Range &amp; Accuracy, and Pronunciation.
          </p>
        </div>

        <div className="ielts-card">
          <ScoreReveal score={score} />

          <div style={{ display: "flex", gap: "var(--space-4)", justifyContent: "center", marginTop: "var(--space-8)" }}>
            <button
              type="button"
              className="ielts-primary-btn"
              onClick={() => {
                const reportId = parentSessionId || sessionId;
                if (reportId) {
                  navigate(`/report/${reportId}`);
                }
              }}
            >
              📊 View Detailed Analytics Report
            </button>

            <button
              type="button"
              className="ielts-secondary-btn"
              onClick={() => send({ type: "RETRY" })}
            >
              🔄 Practice Another Test
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── View: Active Live Test (Part 1, Part 2, Part 3, Scoring) ─────────────
  return (
    <div className="ielts-container">
      {/* Top Part Navigation & Step Status */}
      <div className="ielts-stage-nav">
        <PartIndicator currentPart={prompt?.part ?? 1} />
        <span className="ielts-header__badge">Target Band {targetBand.toFixed(1)}</span>
      </div>

      <AnimatePresence mode="wait">
        {/* Part 1: Intro */}
        {state.matches("part1Intro") && (
          <motion.div className="ielts-stage-card" key="intro" {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 1 · Introduction</div>
            <h2 className="ielts-stage-question">Let's begin with some questions about yourself.</h2>
            {voice.phase === "ai-speaking" ? (
              <p className="ielts-stage-hint">Examiner is speaking…</p>
            ) : (
              <button
                type="button"
                className="ielts-primary-btn"
                onClick={() => send({ type: "INTRO_FINISHED" })}
                disabled={isBusy}
              >
                I'm Ready →
              </button>
            )}
          </motion.div>
        )}

        {/* Part 1: Q&A */}
        {state.matches("part1QA") && prompt?.question && (
          <motion.div className="ielts-stage-card" key={prompt.question} {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 1 · Question</div>
            <h2 className="ielts-stage-question">"{prompt.question}"</h2>
            {renderVoiceController()}
          </motion.div>
        )}

        {/* Part 2: Cue Card Acknowledgment */}
        {state.matches("part2CueCard") && prompt?.cue_card && (
          <motion.div className="ielts-stage-card" key="cue-card" {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 2 · Individual Long Turn</div>
            <CueCard cueCard={prompt.cue_card} />
            {voice.phase === "ai-speaking" ? (
              <p className="ielts-stage-hint">Listening to examiner instructions…</p>
            ) : (
              <button
                type="button"
                className="ielts-primary-btn"
                onClick={() => send({ type: "CUE_CARD_ACKNOWLEDGED" })}
                disabled={isBusy}
              >
                Start 1-Minute Preparation ⏱️
              </button>
            )}
          </motion.div>
        )}

        {/* Part 2: 1-Minute Preparation */}
        {state.matches("part2Prep") && (
          <motion.div className="ielts-stage-card" key="prep" {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 2 · Preparation Time</div>
            <PrepTimer label="Preparation Time" remainingSeconds={prepRemaining} totalSeconds={60} />
            <p className="ielts-stage-hint">
              Think about what you want to say. You can jot down mental notes before your 2-minute turn.
            </p>
          </motion.div>
        )}

        {/* Part 2: Speaking */}
        {state.matches("part2Speaking") && (
          <motion.div className="ielts-stage-card" key="speaking" {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 2 · Your Speaking Turn</div>
            <PrepTimer
              label="Speaking Time"
              remainingSeconds={speakingRemaining}
              totalSeconds={120}
              warnAtRatio={0.15}
            />
            <h2 className="ielts-stage-question" style={{ fontSize: "1.25rem" }}>
              {prompt?.cue_card?.topic}
            </h2>
            {renderVoiceController()}
          </motion.div>
        )}

        {/* Part 2: Follow-up Question */}
        {state.matches("part2FollowUp") && (
          <motion.div className="ielts-stage-card" key="followup" {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 2 · Follow-Up Question</div>
            <h2 className="ielts-stage-question">{prompt?.question || "Let's explore that topic a bit more."}</h2>
            {renderVoiceController()}
          </motion.div>
        )}

        {/* Part 3: In-Depth Discussion */}
        {state.matches("part3Discussion") && prompt?.question && (
          <motion.div className="ielts-stage-card" key={prompt.question} {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Part 3 · Two-Way Discussion</div>
            <h2 className="ielts-stage-question">"{prompt.question}"</h2>
            {renderVoiceController()}
          </motion.div>
        )}

        {/* Scoring State */}
        {(state.matches("scoring") || state.matches("fetchingScore")) && (
          <motion.div className="ielts-stage-card" key="scoring" {...FADE_TRANSITION}>
            <div className="ielts-stage-badge ielts-stage-badge--active">Evaluating Test</div>
            <h2 className="ielts-stage-question">Calculating Holistic Band Score…</h2>
            <p className="ielts-stage-hint">
              The AI examiner is analyzing your fluency, grammar complexity, vocabulary richness, and pronunciation accuracy across all test responses.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
