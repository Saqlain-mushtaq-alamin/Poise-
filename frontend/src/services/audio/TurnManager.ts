/**
 * Voice turn-taking state machine, per the Phase 3 spec's §3.6:
 *
 *   IDLE → [user speaks] → LISTENING → [silence] → PROCESSING
 *   PROCESSING → [TTS starts] → SPEAKING → [TTS ends] → IDLE
 *   SPEAKING → [user speaks, sustained] → LISTENING (barge-in, interrupts TTS)
 *
 * Deliberately has zero dependency on the DOM, Web Audio, or wall-clock
 * timers — it's fed VAD frames with explicit timestamps (matching what
 * `/voice/vad/status` sends over the WebSocket) and drives everything from
 * that, which is what makes it fully deterministic to unit test.
 */

export type TurnState = "idle" | "listening" | "processing" | "speaking";

const DEFAULT_BARGE_IN_DEBOUNCE_MS = 300;

export interface TurnManagerOptions {
  /** How long continuous speech must be sustained during SPEAKING before
   * it counts as a deliberate barge-in rather than a cough/noise burst. */
  bargeInDebounceMs?: number;
  onStateChange?: (next: TurnState, prev: TurnState) => void;
  /** Called exactly once, at the moment a barge-in is confirmed — this is
   * where the caller should stop TTS playback (see TTSPlayback.stop()). */
  onInterruptPlayback?: () => void;
}

export class TurnManager {
  private _state: TurnState = "idle";
  private bargeInSpeechStartMs: number | null = null;
  private readonly bargeInDebounceMs: number;
  private readonly options: TurnManagerOptions;

  constructor(options: TurnManagerOptions = {}) {
    this.options = options;
    this.bargeInDebounceMs = options.bargeInDebounceMs ?? DEFAULT_BARGE_IN_DEBOUNCE_MS;
  }

  get state(): TurnState {
    return this._state;
  }

  private setState(next: TurnState): void {
    if (next === this._state) return;
    const prev = this._state;
    this._state = next;
    this.options.onStateChange?.(next, prev);
  }

  /**
   * Feed one VAD frame. `timestampMs` must be monotonically increasing
   * (matches the `timestamp_ms` field on each `/voice/vad/status` message).
   */
  reportVadFrame(isSpeech: boolean, timestampMs: number): void {
    switch (this._state) {
      case "idle":
        if (isSpeech) this.setState("listening");
        break;

      case "listening":
        if (!isSpeech) this.setState("processing");
        break;

      case "speaking":
        if (isSpeech) {
          if (this.bargeInSpeechStartMs === null) {
            this.bargeInSpeechStartMs = timestampMs;
          } else if (timestampMs - this.bargeInSpeechStartMs >= this.bargeInDebounceMs) {
            this.bargeInSpeechStartMs = null;
            this.options.onInterruptPlayback?.();
            this.setState("listening");
          }
        } else {
          // Speech stopped before crossing the debounce threshold — treat
          // it as noise, not an intentional interruption.
          this.bargeInSpeechStartMs = null;
        }
        break;

      case "processing":
        // Nothing playing yet, so there's nothing to interrupt; VAD frames
        // are ignored here by design.
        break;
    }
  }

  /** Call once the response pipeline is ready and TTS is about to start. */
  startSpeaking(): void {
    if (this._state === "processing") this.setState("speaking");
  }

  /** Call once TTS finishes playing out naturally (not via barge-in). */
  endSpeaking(): void {
    if (this._state === "speaking") this.setState("idle");
  }

  reset(): void {
    this.bargeInSpeechStartMs = null;
    this.setState("idle");
  }
}
