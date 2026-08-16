import { AnimatePresence, motion } from "framer-motion";
import { useState, useEffect, useCallback, useRef } from "react";
import { CueCard } from "../components/ielts/CueCard";
import { PartIndicator } from "../components/ielts/PartIndicator";
import { PrepTimer } from "../components/ielts/PrepTimer";
import { ScoreReveal } from "../components/ielts/ScoreReveal";
import { useIELTSSession } from "../hooks/useIELTSSession";
import { useVoiceInterview } from "../hooks/useVoiceInterview";
import type { PoiseAPI } from "../lib/api";

const FADE = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
  transition: { duration: 0.25 },
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
    <div className="ielts-answer-area" style={{ marginTop: "1.5rem" }}>
      {voice.phase === "listening" ? (
        <div className="vcir__transcript-area">
          <div className="vcir__transcript-label" style={{ marginBottom: "0.5rem", fontSize: "0.9rem", color: "var(--color-text-muted)" }}>
            <span className={`vcir__transcript-dot${voice.isSpeaking ? " vcir__transcript-dot--active" : ""}`} />
            {voice.isSpeaking ? "Speaking… (pause to submit)" : voice.transcript ? "Pause detected — will submit shortly" : "Listening for your answer…"}
          </div>
          <div className="vcir__transcript-text" style={{ fontSize: "1.1rem", fontStyle: "italic", minHeight: "1.5rem" }}>
            <span className="vcir__transcript-final">{voice.transcript}</span>
            {voice.interimTranscript && (
              <span className="vcir__transcript-interim" style={{ opacity: 0.6 }}> {voice.interimTranscript}</span>
            )}
          </div>
          <button style={{ marginTop: "1rem", fontSize: "0.85rem", padding: "0.4rem 0.8rem", borderRadius: "16px" }} onClick={() => setShowManualInput(v => !v)}>
            {showManualInput ? "Hide keyboard" : "Type instead"}
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
           {!isBusy && voice.phase !== "ai-speaking" && (
             <button onClick={() => { voice.clearTranscript(); voice.startListening(); }}>Start Microphone</button>
           )}
           <button onClick={() => setShowManualInput(v => !v)}>{showManualInput ? "Hide keyboard" : "Type instead"}</button>
        </div>
      )}

      {showManualInput && (
        <div style={{ marginTop: "1rem" }}>
          <textarea
            value={manualAnswer}
            onChange={e => setManualAnswer(e.target.value)}
            style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid var(--color-border-subtle)", backgroundColor: "var(--color-bg-elevated)", color: "var(--color-text)", fontSize: "1rem" }}
            rows={3}
            placeholder="Type your answer here..."
            onKeyDown={e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleManualSend(); }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.5rem" }}>
             <span style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>Ctrl+Enter to send</span>
             <button onClick={handleManualSend} disabled={isBusy || !manualAnswer.trim()}>
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
      <div className="ielts-page">
        <h1>IELTS Speaking Practice</h1>
        <div className="settings-card__warning" style={{ marginTop: "1.5rem", padding: "1.25rem 1.5rem", borderRadius: "12px" }}>
          ⚠️ Sidecar not connected — please wait a moment while the backend initialises, then
          refresh this page.
        </div>
      </div>
    );
  }

  // ---- Error state ----
  if (state.matches("error")) {
    return (
      <div className="ielts-page">
        <h2>Something went wrong</h2>
        <p className="settings-card__warning" style={{ marginTop: "1rem" }}>{error}</p>
        <button style={{ marginTop: "1.5rem" }} onClick={() => send({ type: "RETRY" })}>Try again</button>
      </div>
    );
  }

  // ---- Idle: setup screen ----
  if (state.matches("idle")) {
    return (
      <div className="ielts-page">
        <h1>IELTS Speaking Practice</h1>
        <p>A full Part 1 / 2 / 3 simulation, scored against the four official criteria.</p>
        <div className="settings-card" style={{ marginTop: "1.5rem", maxWidth: "420px" }}>
          <h3>Session setup</h3>
          <div className="audio-settings__row">
            <label htmlFor="target-band">Target band score</label>
            <input
              id="target-band"
              type="number"
              min={0}
              max={9}
              step={0.5}
              value={targetBand}
              onChange={(e) => setTargetBand(Number(e.target.value))}
              style={{ width: "6rem" }}
            />
          </div>
          <button
            style={{ marginTop: "1rem", width: "100%" }}
            onClick={() => send({ type: "CREATE", targetBand })}
            disabled={isBusy}
          >
            {isBusy ? "Creating session…" : "Create session"}
          </button>
        </div>
      </div>
    );
  }

  // ---- Creating ----
  if (state.matches("creating")) {
    return (
      <div className="ielts-page">
        <h1>IELTS Speaking Practice</h1>
        <p style={{ opacity: 0.7, marginTop: "1rem" }}>Creating your session…</p>
      </div>
    );
  }

  // ---- Ready to start ----
  if (state.matches("readyToStart")) {
    return (
      <div className="ielts-page">
        <h1>Ready when you are</h1>
        <p>The test takes about 11–14 minutes, just like the real IELTS Speaking test.</p>
        <button
          style={{ marginTop: "1.5rem" }}
          onClick={() => send({ type: "BEGIN" })}
          disabled={isBusy}
        >
          {isBusy ? "Starting…" : "Begin test"}
        </button>
      </div>
    );
  }

  // ---- Complete ----
  if (state.matches("complete") && score) {
    return (
      <div className="ielts-page">
        <ScoreReveal score={score} />
      </div>
    );
  }

  // ---- Active test ----
  return (
    <div className="ielts-page">
      <PartIndicator currentPart={prompt?.part} />

      <AnimatePresence mode="wait">
        {state.matches("part1Intro") && (
          <motion.div key="intro" {...FADE}>
            <h2>Let's begin with some questions about yourself.</h2>
            {voice.phase === "ai-speaking" ? (
              <p style={{ color: "var(--color-text-muted)" }}>Listening to instructions...</p>
            ) : (
              <button onClick={() => send({ type: "INTRO_FINISHED" })} disabled={isBusy}>
                I'm ready
              </button>
            )}
          </motion.div>
        )}

        {state.matches("part1QA") && prompt?.question && (
          <motion.div key={prompt.question} {...FADE}>
            <p className="ielts-question">{prompt.question}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {state.matches("part2CueCard") && prompt?.cue_card && (
          <motion.div key="cue-card" {...FADE}>
            <CueCard cueCard={prompt.cue_card} />
            {voice.phase === "ai-speaking" ? (
              <p style={{ color: "var(--color-text-muted)", marginTop: "1rem" }}>Listening to instructions...</p>
            ) : (
              <button onClick={() => send({ type: "CUE_CARD_ACKNOWLEDGED" })} disabled={isBusy} style={{ marginTop: "1rem" }}>
                Start preparation
              </button>
            )}
          </motion.div>
        )}

        {state.matches("part2Prep") && (
          <motion.div key="prep" {...FADE} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
            <PrepTimer label="Preparation" remainingSeconds={prepRemaining} totalSeconds={60} />
            <p>Make some notes — you'll speak for up to 2 minutes.</p>
          </motion.div>
        )}

        {state.matches("part2Speaking") && (
          <motion.div key="speaking" {...FADE} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
            <PrepTimer label="Speaking" remainingSeconds={speakingRemaining} totalSeconds={120} warnAtRatio={0.15} />
            <p className="ielts-question">{prompt?.cue_card?.topic}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {state.matches("part2FollowUp") && (
          <motion.div key="followup" {...FADE}>
            <p className="ielts-question">{prompt?.question}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {state.matches("part3Discussion") && prompt?.question && (
          <motion.div key={prompt.question} {...FADE}>
            <p className="ielts-question">{prompt.question}</p>
            {renderAnswerArea()}
          </motion.div>
        )}

        {(state.matches("scoring") || state.matches("fetchingScore")) && (
          <motion.div key="scoring" {...FADE}>
            <p>Calculating your band score…</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
