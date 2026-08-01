import { useMachine } from "@xstate/react";
import { useEffect, useRef, useState } from "react";
import type { PoiseAPI } from "../lib/api";
import { ieltsApi } from "../lib/ieltsApi";
import { ieltsMachine } from "../state/ieltsMachine";

/**
 * Countdown that fires `onDone` once, driven off `time_budget_s` from the
 * current server prompt. Client-side only — the server doesn't enforce
 * timing, it just tells the UI what the budget is (matches the "Web Audio
 * API + worklets... zero-latency" philosophy from the master plan: timing
 * UX lives in the frontend thread).
 */
function useCountdown(totalSeconds: number | null | undefined, active: boolean, onDone: () => void) {
  const [remaining, setRemaining] = useState(totalSeconds ?? 0);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    setRemaining(totalSeconds ?? 0);
  }, [totalSeconds]);

  useEffect(() => {
    if (!active || totalSeconds == null) return;
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onDoneRef.current();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [active, totalSeconds]);

  return remaining;
}

export function useIELTSSession(api: PoiseAPI | null = null) {
  const [state, send] = useMachine(ieltsMachine);

  // Sync ieltsApi IMMEDIATELY so the state machine actors always use the
  // correct sidecar port — even if they fire before the useEffect flush.
  if (api) {
    ieltsApi.syncApi(api);
  }

  // Also keep in sync via effect for hot port changes.
  useEffect(() => {
    if (api) {
      ieltsApi.syncApi(api);
    }
  }, [api]);

  const isPrep = state.matches("part2Prep");
  const isSpeaking = state.matches("part2Speaking");
  const isPart1QA = state.matches("part1QA");
  const isPart3 = state.matches("part3Discussion");

  const prepRemaining = useCountdown(
    isPrep ? state.context.prompt?.time_budget_s : null,
    isPrep,
    () => send({ type: "PREP_TIMER_DONE" })
  );

  const speakingRemaining = useCountdown(
    isSpeaking ? state.context.prompt?.time_budget_s : null,
    isSpeaking,
    () => {
      /* Server enforces the actual cutoff on submitAnswer; the UI timer is
         a visual cue that nudges the candidate to wrap up. */
    }
  );

  return {
    state,
    send,
    prompt: state.context.prompt,
    score: state.context.score,
    error: state.context.error,
    sessionId: state.context.sessionId,
    isPrep,
    isSpeaking,
    isPart1QA,
    isPart3,
    prepRemaining,
    speakingRemaining,
    isBusy: state.matches("creating") || state.matches("starting") || state.matches("advancing") ||
      state.matches("submittingAnswer") || state.matches("fetchingScore"),
  };
}
