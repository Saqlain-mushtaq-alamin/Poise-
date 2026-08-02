import { useCallback, useMemo, useState } from "react";

import type { PoiseAPI } from "../lib/api";
import type { EvaluationRecord, InterviewConfig, InterviewPlan } from "../lib/types";
import { interviewMachine } from "../machines/interviewMachine";
import { createActor } from "xstate";

interface UseInterviewSessionResult {
  machineState: string;
  sessionId: string | null;
  plan: InterviewPlan | null;
  currentMessage: string | null;
  lastFeedback: { score: number; feedback: string; reaction: string | null } | null;
  isComplete: boolean;
  error: string | null;
  busy: boolean;
  createAndStart: (
    resumeId: string,
    jdId: string,
    config: Partial<InterviewConfig>,
    personaId: string
  ) => Promise<void>;
  respondToWarmUp: (text: string) => Promise<void>;
  submitAnswer: (text: string) => Promise<void>;
  endSession: () => Promise<void>;
  fetchEvaluations: () => Promise<EvaluationRecord[]>;
}

/**
 * Orchestration glue over the XState `interviewMachine` and the interview
 * API endpoints. The machine here mirrors the state the backend already
 * tracks — this hook drives it forward from API responses rather than
 * duplicating any transition logic; the source of truth stays server-side.
 */
export function useInterviewSession(api: PoiseAPI | null): UseInterviewSessionResult {
  const actor = useMemo(() => createActor(interviewMachine).start(), []);
  const [, forceRender] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [plan, setPlan] = useState<InterviewPlan | null>(null);
  const [currentMessage, setCurrentMessage] = useState<string | null>(null);
  const [lastFeedback, setLastFeedback] = useState<UseInterviewSessionResult["lastFeedback"]>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const send = useCallback(
    (event: { type: string }) => {
      actor.send(event as never);
      forceRender((n) => n + 1);
    },
    [actor]
  );

  const createAndStart = useCallback(
    async (
      resumeId: string,
      jdId: string,
      config: Partial<InterviewConfig>,
      personaId: string
    ) => {
      if (!api) {
        setError("Sidecar not connected yet");
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const session = await api.createInterviewSession<{ session_id: string; plan: InterviewPlan }>(
          resumeId,
          jdId,
          config,
          personaId
        );
        setSessionId(session.session_id);
        setPlan(session.plan);
        send({ type: "START_SESSION" });
        send({ type: "UPLOAD_COMPLETE" });
        send({ type: "PLAN_GENERATED" });

        send({ type: "BEGIN_INTERVIEW" });
        const started = await api.startInterviewSession<{ message: string }>(session.session_id);
        setCurrentMessage(started.message);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [api, send]
  );

  const respondToWarmUp = useCallback(
    async (text: string) => {
      if (!api || !sessionId) return;
      setBusy(true);
      setError(null);
      try {
        const result = await api.respondToWarmUp<{
          message: string;
          is_complete?: boolean;
          first_question?: string;
        }>(sessionId, text);
        setCurrentMessage(result.message);
        if (result.is_complete) {
          send({ type: "WARM_UP_COMPLETE" });
          if (result.first_question) {
            send({ type: "QUESTION_DELIVERED" });
            setCurrentMessage(result.first_question);
          }
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [api, sessionId, send]
  );

  const submitAnswer = useCallback(
    async (text: string) => {
      if (!api || !sessionId) return;
      setBusy(true);
      setError(null);
      try {
        const result = await api.submitAnswer<{
          score: number;
          feedback: string;
          reaction: string | null;
          next_action: string;
          next_message?: string;
        }>(sessionId, { text });
        setLastFeedback({ score: result.score, feedback: result.feedback, reaction: result.reaction });

        if (result.next_action === "follow_up") {
          send({ type: "EVALUATION_NEEDS_FOLLOW_UP" });
          send({ type: "FOLLOW_UP_DELIVERED" });
          setCurrentMessage(result.next_message ?? null);
        } else if (result.next_action === "next_question") {
          send({ type: "EVALUATION_NEXT_QUESTION" });
          send({ type: "QUESTION_DELIVERED" });
          setCurrentMessage(result.next_message ?? null);
        } else {
          send({ type: "EVALUATION_NEXT_QUESTION" });
          send({ type: "END_INTERVIEW" });
          send({ type: "WRAP_UP_QUESTIONS" });
          send({ type: "SESSION_FINALIZED" });
          setCurrentMessage(null);
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [api, sessionId, send]
  );

  const endSession = useCallback(async () => {
    if (!api || !sessionId) return;
    setBusy(true);
    try {
      await api.endInterviewSession(sessionId);
      send({ type: "END_INTERVIEW" });
      send({ type: "WRAP_UP_QUESTIONS" });
      send({ type: "SESSION_FINALIZED" });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [api, sessionId, send]);

  const fetchEvaluations = useCallback(async () => {
    if (!api || !sessionId) return [];
    return api.getInterviewEvaluations<EvaluationRecord[]>(sessionId);
  }, [api, sessionId]);

  const snapshotValue = actor.getSnapshot().value;
  const machineState =
    typeof snapshotValue === "string" ? snapshotValue : JSON.stringify(snapshotValue);

  return {
    machineState,
    sessionId,
    plan,
    currentMessage,
    lastFeedback,
    isComplete: machineState === "completed" || machineState === "archived",
    error,
    busy,
    createAndStart,
    respondToWarmUp,
    submitAnswer,
    endSession,
    fetchEvaluations,
  };
}
