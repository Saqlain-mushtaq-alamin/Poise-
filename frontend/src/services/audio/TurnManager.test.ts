import { describe, expect, it, vi } from "vitest";

import { TurnManager } from "./TurnManager";

describe("TurnManager", () => {
  it("starts in idle", () => {
    const tm = new TurnManager();
    expect(tm.state).toBe("idle");
  });

  it("idle -> listening when speech starts", () => {
    const tm = new TurnManager();
    tm.reportVadFrame(true, 0);
    expect(tm.state).toBe("listening");
  });

  it("stays idle on a silent frame", () => {
    const tm = new TurnManager();
    tm.reportVadFrame(false, 0);
    expect(tm.state).toBe("idle");
  });

  it("listening -> processing when silence follows speech", () => {
    const tm = new TurnManager();
    tm.reportVadFrame(true, 0);
    tm.reportVadFrame(false, 30);
    expect(tm.state).toBe("processing");
  });

  it("processing -> speaking only via startSpeaking()", () => {
    const tm = new TurnManager();
    tm.reportVadFrame(true, 0);
    tm.reportVadFrame(false, 30);
    expect(tm.state).toBe("processing");

    tm.startSpeaking();
    expect(tm.state).toBe("speaking");
  });

  it("startSpeaking() is a no-op outside processing", () => {
    const tm = new TurnManager();
    tm.startSpeaking();
    expect(tm.state).toBe("idle");
  });

  it("speaking -> idle when endSpeaking() is called", () => {
    const tm = new TurnManager();
    tm.reportVadFrame(true, 0);
    tm.reportVadFrame(false, 30);
    tm.startSpeaking();
    tm.endSpeaking();
    expect(tm.state).toBe("idle");
  });

  it("endSpeaking() is a no-op outside speaking", () => {
    const tm = new TurnManager();
    tm.endSpeaking();
    expect(tm.state).toBe("idle");
  });

  it("ignores VAD frames entirely while processing", () => {
    const tm = new TurnManager();
    tm.reportVadFrame(true, 0);
    tm.reportVadFrame(false, 30); // -> processing
    tm.reportVadFrame(true, 60); // should be ignored
    expect(tm.state).toBe("processing");
  });

  describe("barge-in", () => {
    function speakingManager(onInterruptPlayback: () => void, debounceMs = 300) {
      const tm = new TurnManager({ bargeInDebounceMs: debounceMs, onInterruptPlayback });
      tm.reportVadFrame(true, 0);
      tm.reportVadFrame(false, 30);
      tm.startSpeaking();
      return tm;
    }

    it("does not interrupt on a short speech burst under the debounce threshold", () => {
      const onInterrupt = vi.fn();
      const tm = speakingManager(onInterrupt);

      tm.reportVadFrame(true, 1000);
      tm.reportVadFrame(true, 1100); // only 100ms — under 300ms threshold
      tm.reportVadFrame(false, 1150); // speech stops — should be treated as noise

      expect(onInterrupt).not.toHaveBeenCalled();
      expect(tm.state).toBe("speaking");
    });

    it("interrupts once sustained speech crosses the debounce threshold", () => {
      const onInterrupt = vi.fn();
      const tm = speakingManager(onInterrupt);

      tm.reportVadFrame(true, 1000); // barge-in candidate starts
      tm.reportVadFrame(true, 1150); // 150ms in — not yet
      expect(tm.state).toBe("speaking");

      tm.reportVadFrame(true, 1300); // 300ms in — crosses threshold
      expect(onInterrupt).toHaveBeenCalledTimes(1);
      expect(tm.state).toBe("listening");
    });

    it("resets the barge-in candidate if speech is interrupted by silence first", () => {
      const onInterrupt = vi.fn();
      const tm = speakingManager(onInterrupt);

      tm.reportVadFrame(true, 1000);
      tm.reportVadFrame(false, 1100); // brief silence resets the candidate
      tm.reportVadFrame(true, 1150); // new candidate starts here
      tm.reportVadFrame(true, 1400); // only 250ms since the new candidate — not enough

      expect(onInterrupt).not.toHaveBeenCalled();
      expect(tm.state).toBe("speaking");
    });

    it("only fires onInterruptPlayback once even with frames past the threshold", () => {
      const onInterrupt = vi.fn();
      const tm = speakingManager(onInterrupt);

      tm.reportVadFrame(true, 1000);
      tm.reportVadFrame(true, 1300); // crosses threshold, transitions to listening
      // Now in "listening" state — further speech frames shouldn't re-trigger
      // the (speaking-only) barge-in logic.
      tm.reportVadFrame(true, 1330);

      expect(onInterrupt).toHaveBeenCalledTimes(1);
    });
  });

  describe("onStateChange", () => {
    it("fires with (next, prev) on every transition", () => {
      const onStateChange = vi.fn();
      const tm = new TurnManager({ onStateChange });

      tm.reportVadFrame(true, 0);
      tm.reportVadFrame(false, 30);
      tm.startSpeaking();
      tm.endSpeaking();

      expect(onStateChange.mock.calls).toEqual([
        ["listening", "idle"],
        ["processing", "listening"],
        ["speaking", "processing"],
        ["idle", "speaking"],
      ]);
    });

    it("does not fire when a call is a no-op", () => {
      const onStateChange = vi.fn();
      const tm = new TurnManager({ onStateChange });

      tm.reportVadFrame(false, 0); // idle -> idle, no-op
      tm.endSpeaking(); // no-op outside speaking

      expect(onStateChange).not.toHaveBeenCalled();
    });
  });

  describe("reset", () => {
    it("returns to idle and clears any pending barge-in candidate", () => {
      const onInterrupt = vi.fn();
      const tm = new TurnManager({ onInterruptPlayback: onInterrupt });
      tm.reportVadFrame(true, 0);
      tm.reportVadFrame(false, 30);
      tm.startSpeaking();
      tm.reportVadFrame(true, 100); // barge-in candidate started, not yet confirmed

      tm.reset();
      expect(tm.state).toBe("idle");

      // Fresh cycle after reset behaves like a clean start.
      tm.reportVadFrame(true, 10_000);
      expect(tm.state).toBe("listening");
    });
  });
});
