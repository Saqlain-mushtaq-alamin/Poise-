import { assign, fromPromise, setup } from "xstate";
import { ieltsApi } from "../lib/ieltsApi";
import type { AnswerResult, CurrentPrompt, IELTSBandScore, IELTSSessionDetail } from "../types/ielts";

interface IELTSMachineContext {
  sessionId: string | null;       // IELTS-internal id (ielts_sessions.id)
  parentSessionId: string | null; // Parent sessions.id — used for /scoring/report
  prompt: CurrentPrompt | null;
  score: IELTSBandScore | null;
  error: string | null;
  targetBand: number;
  topicsPreference?: string;
}

type IELTSMachineEvent =
  | { type: "CREATE"; targetBand: number; topicsPreference?: string }
  | { type: "BEGIN" }
  | { type: "PREP_TIMER_DONE" }
  | { type: "CUE_CARD_ACKNOWLEDGED" }
  | { type: "INTRO_FINISHED" }
  | { type: "ANSWER_SUBMITTED"; audioPath: string; transcript: string }
  | { type: "RETRY" };

/**
 * Mirrors backend/app/services/ielts/state_machine.py 1:1 so the UI and
 * server are never out of sync: every UI state name matches the
 * `IELTSState` enum value returned in `current_prompt.state`.
 */
export const ieltsMachine = setup({
  types: {
    context: {} as IELTSMachineContext,
    events: {} as IELTSMachineEvent,
  },
  actors: {
    createSession: fromPromise<
      IELTSSessionDetail,
      { targetBand: number; topicsPreference?: string }
    >(({ input }) => ieltsApi.createSession(input.targetBand, input.topicsPreference)),
    startSession: fromPromise<IELTSSessionDetail, { sessionId: string }>(({ input }) =>
      ieltsApi.startSession(input.sessionId)
    ),
    advanceSession: fromPromise<IELTSSessionDetail, { sessionId: string }>(({ input }) =>
      ieltsApi.advance(input.sessionId)
    ),
    submitAnswer: fromPromise<
      AnswerResult,
      { sessionId: string; audioPath: string; transcript: string }
    >(({ input }) => ieltsApi.submitAnswer(input.sessionId, input.audioPath, input.transcript)),
    fetchScore: fromPromise<IELTSBandScore, { sessionId: string }>(({ input }) =>
      ieltsApi.getScore(input.sessionId)
    ),
  },
}).createMachine({
  id: "ielts",
  initial: "idle",
  context: {
    sessionId: null,
    parentSessionId: null,
    prompt: null,
    score: null,
    error: null,
    targetBand: 6.5,
  },
  states: {
    idle: {
      on: {
        CREATE: { target: "creating" },
      },
    },
    creating: {
      invoke: {
        src: "createSession",
        input: ({ event }) => {
          if (event.type !== "CREATE") throw new Error("unreachable");
          return { targetBand: event.targetBand, topicsPreference: event.topicsPreference };
        },
        onDone: {
          target: "readyToStart",
          actions: assign({
            sessionId: ({ event }) => event.output.id,
            // session_id is the parent sessions.id — used by /scoring/report
            parentSessionId: ({ event }) => event.output.session_id ?? event.output.id,
          }),
        },
        onError: { target: "error", actions: assign({ error: ({ event }) => String(event.error) }) },
      },
    },
    readyToStart: {
      on: { BEGIN: "starting" },
    },
    starting: {
      invoke: {
        src: "startSession",
        input: ({ context }) => ({ sessionId: context.sessionId! }),
        onDone: {
          target: "part1Intro",
          actions: assign({ prompt: ({ event }) => event.output.current_prompt ?? null }),
        },
        onError: { target: "error", actions: assign({ error: ({ event }) => String(event.error) }) },
      },
    },
    part1Intro: {
      on: { INTRO_FINISHED: "advancing" },
    },
    part1QA: {
      on: { ANSWER_SUBMITTED: "submittingAnswer" },
    },
    part2CueCard: {
      on: { CUE_CARD_ACKNOWLEDGED: "advancing" },
    },
    part2Prep: {
      on: { PREP_TIMER_DONE: "advancing" },
    },
    part2Speaking: {
      on: { ANSWER_SUBMITTED: "submittingAnswer" },
    },
    part2FollowUp: {
      on: { ANSWER_SUBMITTED: "submittingAnswer" },
    },
    part3Discussion: {
      on: { ANSWER_SUBMITTED: "submittingAnswer" },
    },
    advancing: {
      invoke: {
        src: "advanceSession",
        input: ({ context }) => ({ sessionId: context.sessionId! }),
        onDone: {
          target: "routing",
          actions: assign({ prompt: ({ event }) => event.output.current_prompt ?? null }),
        },
        onError: { target: "error", actions: assign({ error: ({ event }) => String(event.error) }) },
      },
    },
    submittingAnswer: {
      invoke: {
        src: "submitAnswer",
        input: ({ context, event }) => {
          if (event.type !== "ANSWER_SUBMITTED") throw new Error("unreachable");
          return { sessionId: context.sessionId!, audioPath: event.audioPath, transcript: event.transcript };
        },
        onDone: {
          target: "routing",
          actions: assign({ prompt: ({ event }) => event.output.next_prompt ?? null }),
        },
        onError: { target: "error", actions: assign({ error: ({ event }) => String(event.error) }) },
      },
    },
    // Central router: reads context.prompt.state (set by the previous
    // transition) and dispatches to the matching UI state.
    routing: {
      always: [
        { guard: ({ context }) => context.prompt?.state === "part1_qa", target: "part1QA" },
        { guard: ({ context }) => context.prompt?.state === "part2_cue_card", target: "part2CueCard" },
        { guard: ({ context }) => context.prompt?.state === "part2_prep", target: "part2Prep" },
        { guard: ({ context }) => context.prompt?.state === "part2_speaking", target: "part2Speaking" },
        { guard: ({ context }) => context.prompt?.state === "part2_follow_up", target: "part2FollowUp" },
        { guard: ({ context }) => context.prompt?.state === "part3_discussion", target: "part3Discussion" },
        { guard: ({ context }) => context.prompt?.state === "scoring", target: "scoring" },
        { guard: ({ context }) => context.prompt?.state === "complete", target: "fetchingScore" },
        { target: "error", actions: assign({ error: () => "Unrecognized server state" }) },
      ],
    },
    scoring: {
      // Server finalizes scoring synchronously as part of the last
      // `/answer` call; this state is a brief "Calculating your band
      // score..." beat before we fetch it.
      after: { 400: "fetchingScore" },
    },
    fetchingScore: {
      invoke: {
        src: "fetchScore",
        input: ({ context }) => ({ sessionId: context.sessionId! }),
        onDone: {
          target: "complete",
          actions: assign({ score: ({ event }) => event.output }),
        },
        onError: { target: "error", actions: assign({ error: ({ event }) => String(event.error) }) },
      },
    },
    complete: { type: "final" },
    error: {
      on: { RETRY: "idle" },
    },
  },
});
