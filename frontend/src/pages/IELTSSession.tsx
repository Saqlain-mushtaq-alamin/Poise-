import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { CueCard } from "../components/ielts/CueCard";
import { PartIndicator } from "../components/ielts/PartIndicator";
import { PrepTimer } from "../components/ielts/PrepTimer";
import { ScoreReveal } from "../components/ielts/ScoreReveal";
import { useIELTSSession } from "../hooks/useIELTSSession";
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

  // Placeholder answer submission — real voice recording wired in Phase 3
  const submitFakeAnswer = () => {
    send({
      type: "ANSWER_SUBMITTED",
      audioPath: "/tmp/recording.wav",
      transcript: "(transcript from voice pipeline)",
    });
  };

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
            <button onClick={() => send({ type: "INTRO_FINISHED" })} disabled={isBusy}>
              I'm ready
            </button>
          </motion.div>
        )}

        {state.matches("part1QA") && prompt?.question && (
          <motion.div key={prompt.question} {...FADE}>
            <p className="ielts-question">{prompt.question}</p>
            <button onClick={submitFakeAnswer} disabled={isBusy}>Submit answer</button>
          </motion.div>
        )}

        {state.matches("part2CueCard") && prompt?.cue_card && (
          <motion.div key="cue-card" {...FADE}>
            <CueCard cueCard={prompt.cue_card} />
            <button onClick={() => send({ type: "CUE_CARD_ACKNOWLEDGED" })} disabled={isBusy}>
              Start preparation
            </button>
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
            <button onClick={submitFakeAnswer} disabled={isBusy}>Finish speaking</button>
          </motion.div>
        )}

        {state.matches("part2FollowUp") && (
          <motion.div key="followup" {...FADE}>
            <p className="ielts-question">{prompt?.question}</p>
            <button onClick={submitFakeAnswer} disabled={isBusy}>Submit answer</button>
          </motion.div>
        )}

        {state.matches("part3Discussion") && prompt?.question && (
          <motion.div key={prompt.question} {...FADE}>
            <p className="ielts-question">{prompt.question}</p>
            <button onClick={submitFakeAnswer} disabled={isBusy}>Submit answer</button>
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
