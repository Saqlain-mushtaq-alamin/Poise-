import { useState } from "react";

interface InterviewRoomProps {
  currentMessage: string | null;
  lastFeedback: { score: number; feedback: string; reaction: string | null } | null;
  isComplete: boolean;
  busy: boolean;
  machineState: string;
  onSubmitWarmUp: (text: string) => void;
  onSubmitAnswer: (text: string) => void;
  onEnd: () => void;
}

const WARM_UP_STATE = "warmUp";

function isAnsweringState(machineState: string): boolean {
  return machineState.includes("listening") || machineState.includes("followUp");
}

export function InterviewRoom({
  currentMessage,
  lastFeedback,
  isComplete,
  busy,
  machineState,
  onSubmitWarmUp,
  onSubmitAnswer,
  onEnd,
}: InterviewRoomProps) {
  const [draft, setDraft] = useState("");
  const isWarmUp = machineState === WARM_UP_STATE;

  function handleSubmit() {
    if (!draft.trim()) return;
    if (isWarmUp) {
      onSubmitWarmUp(draft);
    } else {
      onSubmitAnswer(draft);
    }
    setDraft("");
  }

  if (isComplete) {
    return (
      <div className="interview-room">
        <h2>Interview complete</h2>
        <p className="page__placeholder-note">
          Great work. A detailed scoring report arrives in Phase 8 (Scoring &amp; Progress) — for
          now, your answers and evaluations are saved and available via the API.
        </p>
      </div>
    );
  }

  return (
    <div className="interview-room">
      <div className="interview-room__transcript">
        {currentMessage && <p className="interview-room__message">{currentMessage}</p>}
        {lastFeedback && (
          <p className="interview-room__feedback">
            {lastFeedback.reaction && <em>{lastFeedback.reaction}</em>} {lastFeedback.feedback}
          </p>
        )}
      </div>

      <div className="interview-room__input">
        <label htmlFor="answer-draft" className="sr-only">
          Your response
        </label>
        <textarea
          id="answer-draft"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={isWarmUp ? "Type your reply..." : "Type your answer..."}
          rows={5}
          disabled={busy || !isAnsweringState(machineState) && !isWarmUp}
        />
        <div className="interview-room__actions">
          <button type="button" onClick={handleSubmit} disabled={busy || !draft.trim()}>
            {busy ? "Sending\u2026" : "Send"}
          </button>
          <button type="button" onClick={onEnd} disabled={busy} className="interview-room__end">
            End interview
          </button>
        </div>
      </div>
    </div>
  );
}
