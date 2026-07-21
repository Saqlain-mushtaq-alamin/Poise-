import { createActor } from "xstate";
import { describe, expect, it } from "vitest";

import { interviewMachine } from "./interviewMachine";

function actorAt(...events: { type: string }[]) {
  const actor = createActor(interviewMachine).start();
  for (const event of events) {
    actor.send(event as never);
  }
  return actor;
}

describe("interviewMachine", () => {
  it("starts in created", () => {
    const actor = createActor(interviewMachine).start();
    expect(actor.getSnapshot().value).toBe("created");
  });

  it("happy path through the full lifecycle", () => {
    const actor = actorAt(
      { type: "START_SESSION" },
      { type: "UPLOAD_COMPLETE" },
      { type: "PLAN_GENERATED" },
      { type: "BEGIN_INTERVIEW" },
      { type: "WARM_UP_COMPLETE" }
    );
    expect(actor.getSnapshot().value).toEqual({ inProgress: "asking" });

    actor.send({ type: "QUESTION_DELIVERED" });
    expect(actor.getSnapshot().value).toEqual({ inProgress: "listening" });

    actor.send({ type: "ANSWER_RECEIVED" });
    expect(actor.getSnapshot().value).toEqual({ inProgress: "evaluating" });

    actor.send({ type: "EVALUATION_NEXT_QUESTION" });
    expect(actor.getSnapshot().value).toEqual({ inProgress: "asking" });

    actor.send({ type: "END_INTERVIEW" });
    expect(actor.getSnapshot().value).toBe("wrappingUp");

    actor.send({ type: "WRAP_UP_QUESTIONS" });
    expect(actor.getSnapshot().value).toBe("closingChat");

    actor.send({ type: "SESSION_FINALIZED" });
    expect(actor.getSnapshot().value).toBe("completed");

    actor.send({ type: "ARCHIVE" });
    expect(actor.getSnapshot().value).toBe("archived");
  });

  it("follow-up loop", () => {
    const actor = actorAt(
      { type: "START_SESSION" },
      { type: "UPLOAD_COMPLETE" },
      { type: "PLAN_GENERATED" },
      { type: "BEGIN_INTERVIEW" },
      { type: "WARM_UP_COMPLETE" },
      { type: "QUESTION_DELIVERED" },
      { type: "ANSWER_RECEIVED" }
    );
    expect(actor.getSnapshot().value).toEqual({ inProgress: "evaluating" });

    actor.send({ type: "EVALUATION_NEEDS_FOLLOW_UP" });
    expect(actor.getSnapshot().value).toEqual({ inProgress: "followUp" });

    actor.send({ type: "FOLLOW_UP_DELIVERED" });
    expect(actor.getSnapshot().value).toEqual({ inProgress: "listening" });
  });

  it("time_exceeded ends the interview from any in-progress substate", () => {
    const actor = actorAt(
      { type: "START_SESSION" },
      { type: "UPLOAD_COMPLETE" },
      { type: "PLAN_GENERATED" },
      { type: "BEGIN_INTERVIEW" },
      { type: "WARM_UP_COMPLETE" },
      { type: "QUESTION_DELIVERED" }
    );
    expect(actor.getSnapshot().value).toEqual({ inProgress: "listening" });

    actor.send({ type: "TIME_EXCEEDED" });
    expect(actor.getSnapshot().value).toBe("wrappingUp");
  });

  it("invalid events are ignored, not crashing, and stay in the same state", () => {
    const actor = createActor(interviewMachine).start();
    actor.send({ type: "ANSWER_RECEIVED" }); // nonsensical from `created`
    expect(actor.getSnapshot().value).toBe("created");
  });

  describe("pause/resume", () => {
    it("pausing from warmUp resumes back to warmUp", () => {
      const actor = actorAt(
        { type: "START_SESSION" },
        { type: "UPLOAD_COMPLETE" },
        { type: "PLAN_GENERATED" },
        { type: "BEGIN_INTERVIEW" }
      );
      expect(actor.getSnapshot().value).toBe("warmUp");

      actor.send({ type: "PAUSE" });
      expect(actor.getSnapshot().value).toBe("paused");

      actor.send({ type: "RESUME" });
      expect(actor.getSnapshot().value).toBe("warmUp");
    });

    it("pausing from inProgress.listening resumes back to exactly that substate", () => {
      const actor = actorAt(
        { type: "START_SESSION" },
        { type: "UPLOAD_COMPLETE" },
        { type: "PLAN_GENERATED" },
        { type: "BEGIN_INTERVIEW" },
        { type: "WARM_UP_COMPLETE" },
        { type: "QUESTION_DELIVERED" }
      );
      expect(actor.getSnapshot().value).toEqual({ inProgress: "listening" });

      actor.send({ type: "PAUSE" });
      expect(actor.getSnapshot().value).toBe("paused");

      actor.send({ type: "RESUME" });
      expect(actor.getSnapshot().value).toEqual({ inProgress: "listening" });
    });

    it("pausing from inProgress.followUp resumes back to followUp specifically", () => {
      const actor = actorAt(
        { type: "START_SESSION" },
        { type: "UPLOAD_COMPLETE" },
        { type: "PLAN_GENERATED" },
        { type: "BEGIN_INTERVIEW" },
        { type: "WARM_UP_COMPLETE" },
        { type: "QUESTION_DELIVERED" },
        { type: "ANSWER_RECEIVED" },
        { type: "EVALUATION_NEEDS_FOLLOW_UP" }
      );
      expect(actor.getSnapshot().value).toEqual({ inProgress: "followUp" });

      actor.send({ type: "PAUSE" });
      actor.send({ type: "RESUME" });
      expect(actor.getSnapshot().value).toEqual({ inProgress: "followUp" });
    });
  });

  it("each actor instance has independent state", () => {
    const actor1 = createActor(interviewMachine).start();
    const actor2 = createActor(interviewMachine).start();

    actor1.send({ type: "START_SESSION" });

    expect(actor1.getSnapshot().value).toBe("setup");
    expect(actor2.getSnapshot().value).toBe("created");
  });
});
