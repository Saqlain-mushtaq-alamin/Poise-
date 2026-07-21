import { assign, createMachine } from "xstate";

/**
 * Frontend mirror of backend/app/services/state_machine.py's
 * SessionStateMachine — same states, same transitions, same names,
 * so a developer reading one understands the other. The backend is the
 * source of truth for what's actually persisted; this machine drives the
 * UI (which screen to show, whether the mic should be listening, etc.)
 * and should be kept in sync with it by hand until Phase 9's shared-
 * contract codegen exists.
 *
 * Pure state logic — no network calls — so this is fully unit-testable
 * with XState's `createActor`, same spirit as TurnManager in Phase 3.
 */

export interface InterviewContext {
  pausedFrom: string | null;
}

export type InterviewEvent =
  | { type: "START_SESSION" }
  | { type: "UPLOAD_COMPLETE" }
  | { type: "PLAN_GENERATED" }
  | { type: "BEGIN_INTERVIEW" }
  | { type: "WARM_UP_COMPLETE" }
  | { type: "QUESTION_DELIVERED" }
  | { type: "ANSWER_RECEIVED" }
  | { type: "EVALUATION_NEEDS_FOLLOW_UP" }
  | { type: "EVALUATION_NEXT_QUESTION" }
  | { type: "FOLLOW_UP_DELIVERED" }
  | { type: "END_INTERVIEW" }
  | { type: "TIME_EXCEEDED" }
  | { type: "WRAP_UP_QUESTIONS" }
  | { type: "SESSION_FINALIZED" }
  | { type: "ARCHIVE" }
  | { type: "PAUSE" }
  | { type: "RESUME" };

export const interviewMachine = createMachine({
  id: "interview",
  types: {} as {
    context: InterviewContext;
    events: InterviewEvent;
  },
  context: { pausedFrom: null },
  initial: "created",
  states: {
    created: {
      on: { START_SESSION: "setup" },
    },
    setup: {
      on: { UPLOAD_COMPLETE: "planning" },
    },
    planning: {
      on: { PLAN_GENERATED: "ready" },
    },
    ready: {
      on: { BEGIN_INTERVIEW: "warmUp" },
    },
    warmUp: {
      on: {
        WARM_UP_COMPLETE: "inProgress.asking",
        PAUSE: { target: "paused", actions: assign({ pausedFrom: "warmUp" }) },
      },
    },
    inProgress: {
      initial: "asking",
      states: {
        asking: {
          on: {
            QUESTION_DELIVERED: "listening",
            PAUSE: {
              target: "#interview.paused",
              actions: assign({ pausedFrom: "asking" }),
            },
          },
        },
        listening: {
          on: {
            ANSWER_RECEIVED: "evaluating",
            PAUSE: {
              target: "#interview.paused",
              actions: assign({ pausedFrom: "listening" }),
            },
          },
        },
        evaluating: {
          on: {
            EVALUATION_NEEDS_FOLLOW_UP: "followUp",
            EVALUATION_NEXT_QUESTION: "asking",
            PAUSE: {
              target: "#interview.paused",
              actions: assign({ pausedFrom: "evaluating" }),
            },
          },
        },
        followUp: {
          on: {
            FOLLOW_UP_DELIVERED: "listening",
            PAUSE: {
              target: "#interview.paused",
              actions: assign({ pausedFrom: "followUp" }),
            },
          },
        },
      },
      on: {
        END_INTERVIEW: "wrappingUp",
        TIME_EXCEEDED: "wrappingUp",
      },
    },
    wrappingUp: {
      on: { WRAP_UP_QUESTIONS: "closingChat" },
    },
    closingChat: {
      on: { SESSION_FINALIZED: "completed" },
    },
    completed: {
      on: { ARCHIVE: "archived" },
    },
    archived: { type: "final" },
    paused: {
      on: {
        RESUME: [
          // Resume returns to whichever in-progress sub-state (or warmUp)
          // was captured when PAUSE fired. Falls back to warmUp if
          // somehow nothing was captured, rather than throwing.
          {
            guard: ({ context }) => context.pausedFrom === "warmUp",
            target: "warmUp",
          },
          {
            guard: ({ context }) => context.pausedFrom === "asking",
            target: "inProgress.asking",
          },
          {
            guard: ({ context }) => context.pausedFrom === "listening",
            target: "inProgress.listening",
          },
          {
            guard: ({ context }) => context.pausedFrom === "evaluating",
            target: "inProgress.evaluating",
          },
          {
            guard: ({ context }) => context.pausedFrom === "followUp",
            target: "inProgress.followUp",
          },
          { target: "warmUp" },
        ],
      },
    },
  },
});
