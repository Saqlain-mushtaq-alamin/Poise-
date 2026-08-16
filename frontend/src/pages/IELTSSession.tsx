import { AnimatePresence, motion } from "framer-motion";
import { useState, useEffect, useCallback, useRef } from "react";
import { CueCard } from "../components/ielts/CueCard";
import { PartIndicator } from "../components/ielts/PartIndicator";
import { PrepTimer } from "../components/ielts/PrepTimer";
import { ScoreReveal } from "../components/ielts/ScoreReveal";
import { useIELTSSession } from "../hooks/useIELTSSession";
import { useVoiceInterview } from "../hooks/useVoiceInterview";
import type { PoiseAPI } from "../lib/api";
import "../styles/ielts.css"; // Modern UI styles

const FADE = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
  transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] },
};

interface IELTSSessionProps {
  api: PoiseAPI | null;
}

export default function IELTSSession({ api }: IELTSSessionProps) {
  const {
    state, send, prompt, score, error,
    isPrep: _isPrep, isSpeaking: _isSpeaking, prepRemaining, speakingRemaining, isBusy,
  } = useIELTSSession(api);

  const [targetBand, setTargetBand] = useState(6.5);
  const [manualAnswer, setManualAnswer] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const lastPlayedRef = useRef<string | null>(null);

  const handleAnswerReady = useCallback((text: string) => {
    send({
      type: "ANSWER_SUBMITTED",
      audioPath: "/tmp/dummy.wav",
      transcript: text,
    });
  }, [send]);

  const backendBaseUrl = api?.baseUrlValue || "http://127.0.0.1:8000";

  const voice = useVoiceInterview({
    backendBaseUrl,
    onAnswerReady: handleAnswerReady,
    silenceThresholdSecs: 2.5,
  });

  // ── Voice TTS and auto-listen routing ────────────────────────────────────
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

  const renderAnswerArea = () => (
    <div className="ielts-answer-box">
      {voice.phase === "listening" ? (
        <div style={{ width: "100%", textAlign: "center" }}>
          <div className="ielts-transcript-status" style={{ justifyContent: "center" }}>
            <span className={`ielts-status-dot ${voice.isSpeaking ? "active" : ""}`} />
            {voice.isSpeaking ? "Speaking… (pause to submit)" : voice.transcript ? "Pause detected — will submit shortly" : "Listening for your answer…"}
          </div>
          <div className="ielts-transcript-text">
            <span>{voice.transcript}</span>
            {voice.interimTranscript && (
              <span className="ielts-transcript-interim"> {voice.interimTranscript}</span>
            )}
          </div>
          <button className="ielts-secondary-button" onClick={() => setShowManualInput(v => !v)}>
            {showManualInput ? "Hide keyboard" : "Type instead"}
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: "1rem" }}>
           {!isBusy && voice.phase !== "ai-speaking" && (
             <button className="ielts-action-button" style={{ marginTop: 0 }} onClick={() => { voice.clearTranscript(); voice.startListening(); }}>
               Start Microphone
             </button>
           )}
           <button className="ielts-secondary-button" style={{ marginTop: 0 }} onClick={() => setShowManualInput(v => !v)}>
             {showManualInput ? "Hide keyboard" : "Type instead"}
           </button>
        </div>
      )}

      {showManualInput && (
        <div style={{ width: "100%", marginTop: "1.5rem" }}>
          <textarea
            className="ielts-manual-textarea"
            value={manualAnswer}
            onChange={e => setManualAnswer(e.target.value)}
            placeholder="Type your answer here..."
            onKeyDown={e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleManualSend(); }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
             <span style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>Press Ctrl+Enter to send</span>
             <button className="ielts-action-button" style={{ marginTop: 0, width: "auto", padding: "0.8rem 1.5rem" }} onClick={handleManualSend} disabled={isBusy || !manualAnswer.trim()}>
               Submit Answer
             </button>
          </div>
        </div>
      )}
    </div>
  );

  // ---- Not connected ----
  if (!api) {
    return (
      <div className="ielts-modern-layout">
        <div className="ielts-glass-card">
          <h1 className="ielts-title">IELTS Speaking Practice</h1>
          <div className="settings-card__warning" style={{ marginTop: "1.5rem", padding: "1.25rem 1.5rem", borderRadius: "12px", width: "100%" }}>
            ⚠️ Sidecar not connected — please wait a moment while the backend initialises, then refresh this page.
          </div>
        </div>
      </div>
    );
  }

  // ---- Error state ----
  if (state.matches("error")) {
    return (
      <div className="ielts-modern-layout">
        <div className="ielts-glass-card">
          <h2 className="ielts-title">Something went wrong</h2>
          <p className="ielts-subtitle" style={{ color: "var(--color-accent-danger)" }}>{error}</p>
          <button className="ielts-action-button" onClick={() => send({ type: "RETRY" })}>Try again</button>
        </div>
      </div>
    );
  }

  // ---- Idle: setup screen ----
  if (state.matches("idle")) {
    return (
      <div className="ielts-modern-layout">
        <div className="ielts-glass-card">
          <h1 className="ielts-title">IELTS Speaking Practice</h1>
          <p className="ielts-subtitle">A full Part 1, 2, and 3 simulation, scored holistically against the four official criteria.</p>
          
          <div className="ielts-setup-row">
            <label htmlFor="target-band">Target band score</label>
            <input
              id="target-band"
              className="ielts-setup-input"
              type="number"
              min={0}
              max={9}
              step={0.5}
              value={targetBand}
              onChange={(e) => setTargetBand(Number(e.target.value))}
            />
          </div>
          <button
            className="ielts-action-button"
            onClick={() => send({ type: "CREATE", targetBand })}
            disabled={isBusy}
          >
            {isBusy ? "Creating session…" : "Create Session"}
          </button>
        </div>
      </div>
    );
  }

  // ---- Creating ----
  if (state.matches("creating")) {
    return (
      <div className="ielts-modern-layout">
        <div className="ielts-glass-card">
          <h1 className="ielts-title">IELTS Speaking Practice</h1>
          <p className="ielts-subtitle">Generating authentic topics and configuring your session...</p>
        </div>
      </div>
    );
  }

  // ---- Ready to start ----
  if (state.matches("readyToStart")) {
    return (
      <div className="ielts-modern-layout">
        <div className="ielts-glass-card">
          <h1 className="ielts-title">Ready when you are</h1>
          <p className="ielts-subtitle">The test takes about 11–14 minutes. Ensure your microphone is connected and you are in a quiet room.</p>
          <button
            className="ielts-action-button"
            onClick={() => send({ type: "BEGIN" })}
            disabled={isBusy}
          >
            {isBusy ? "Starting…" : "Begin Test"}
          </button>
        </div>
      </div>
    );
  }

  // ---- Complete ----
  if (state.matches("complete") && score) {
    return (
      <div className="ielts-modern-layout">
        <ScoreReveal score={score} />
      </div>
    );
  }

  // ---- Active test ----
  return (
    <div className="ielts-modern-layout">
      <div style={{ position: "absolute", top: "2rem", left: "2rem" }}>
        <PartIndicator currentPart={prompt?.part} />
      </div>

      <AnimatePresence mode="wait">
        {state.matches("part1Intro") && (
          <motion.div className="ielts-glass-card" key="intro" {...FADE}>
            <h2 className="ielts-question-text" style={{ fontSize: "2rem" }}>Let's begin with some questions about yourself.</h2>
            {voice.phase === "ai-speaking" ? (
              <p className="ielts-subtitle">Listening to examiner instructions...</p>
            ) : (
              <button className="ielts-action-button" onClick={() => send({ type: "INTRO_FINISHED" })} disabled={isBusy}>
                I'm ready
              </button>
            )}
          </motion.div>
        )}

        {state.matches("part1QA") && prompt?.question && (
          <motion.div className="ielts-glass-card" key={prompt.question} {...FADE}>
            <p className="ielts-question-text">{prompt.question}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {state.matches("part2CueCard") && prompt?.cue_card && (
          <motion.div className="ielts-glass-card" key="cue-card" {...FADE}>
            <CueCard cueCard={prompt.cue_card} />
            {voice.phase === "ai-speaking" ? (
              <p className="ielts-subtitle" style={{ marginTop: "1.5rem" }}>Listening to examiner instructions...</p>
            ) : (
              <button className="ielts-action-button" onClick={() => send({ type: "CUE_CARD_ACKNOWLEDGED" })} disabled={isBusy}>
                Start 1-minute preparation
              </button>
            )}
          </motion.div>
        )}

        {state.matches("part2Prep") && (
          <motion.div className="ielts-glass-card" key="prep" {...FADE}>
            <PrepTimer label="Preparation Time" remainingSeconds={prepRemaining} totalSeconds={60} />
            <p className="ielts-subtitle" style={{ marginTop: "1rem" }}>Make some notes — you'll speak for up to 2 minutes.</p>
          </motion.div>
        )}

        {state.matches("part2Speaking") && (
          <motion.div className="ielts-glass-card" key="speaking" {...FADE}>
            <div style={{ width: "100%", display: "flex", justifyContent: "center", marginBottom: "1rem" }}>
              <PrepTimer label="Speaking Time" remainingSeconds={speakingRemaining} totalSeconds={120} warnAtRatio={0.15} />
            </div>
            <p className="ielts-question-text" style={{ fontSize: "1.5rem" }}>{prompt?.cue_card?.topic}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {state.matches("part2FollowUp") && (
          <motion.div className="ielts-glass-card" key="followup" {...FADE}>
            <p className="ielts-question-text">{prompt?.question}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {state.matches("part3Discussion") && prompt?.question && (
          <motion.div className="ielts-glass-card" key={prompt.question} {...FADE}>
            <p className="ielts-question-text">{prompt.question}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {(state.matches("scoring") || state.matches("fetchingScore")) && (
          <motion.div className="ielts-glass-card" key="scoring" {...FADE}>
            <h2 className="ielts-question-text">Calculating your band score…</h2>
            <p className="ielts-subtitle">The examiner is evaluating your performance across all criteria.</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
