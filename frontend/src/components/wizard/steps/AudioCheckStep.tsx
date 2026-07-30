// frontend/src/components/wizard/steps/AudioCheckStep.tsx
//
// Merge notes: reuses the Web Audio VAD worklet from Phase 3
// (frontend/src/lib/audio/vad-worklet.ts). This step only needs a level
// meter + a round-trip through STT, so it imports the smallest possible
// slice of that pipeline — swap `useMicLevel` / `transcribeSample` for the
// real Phase 3 hooks.
import { useEffect, useRef, useState } from "react";
import type { StepProps } from "../FirstRunWizard";
import { invokeSidecar } from "../../../lib/api";

function useMicLevel(active: boolean) {
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    let stream: MediaStream;
    let audioCtx: AudioContext;
    let raf: number;

    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
          analyser.getByteFrequencyData(data);
          const avg = data.reduce((a, b) => a + b, 0) / data.length;
          setLevel(avg / 255);
          raf = requestAnimationFrame(tick);
        };
        tick();
      } catch (err) {
        // Maps to ErrorCategory.MIC_PERMISSION (see lib/errors.ts)
        setError(err instanceof Error ? err.message : "Microphone access denied");
      }
    })();

    return () => {
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      audioCtx?.close();
    };
  }, [active]);

  return { level, error };
}

export function AudioCheckStep({ state, setState, onNext, onSkip }: StepProps) {
  const [phase, setPhase] = useState<"idle" | "listening" | "transcribing" | "confirmed">("idle");
  const [transcript, setTranscript] = useState("");
  const { level, error } = useMicLevel(phase === "listening");
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const startTest = () => {
    setPhase("listening");
    timeoutRef.current = setTimeout(async () => {
      setPhase("transcribing");
      try {
        const res = await invokeSidecar<{ text: string }>("POST", "/voice/transcribe-sample");
        setTranscript(res.text);
        setState((s) => ({ ...s, micTested: true }));
        setPhase("confirmed");
      } catch {
        setPhase("idle");
      }
    }, 3000);
  };

  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  return (
    <div className="wizard-step wizard-step--centered">
      <h1>Audio check</h1>
      <p className="wizard-step__subtitle">Say something so we can confirm your microphone works.</p>

      {error && <p className="wizard-error-text" role="alert">Microphone access denied — check system settings.</p>}

      {!error && (
        <>
          <div className="wizard-mic-meter" aria-hidden="true">
            <div className="wizard-mic-meter__bar" style={{ transform: `scaleX(${Math.max(level, 0.05)})` }} />
          </div>

          {phase === "idle" && (
            <button type="button" className="wizard-btn wizard-btn--primary" onClick={startTest}>
              Say something
            </button>
          )}
          {phase === "listening" && <p role="status">Listening… (3s)</p>}
          {phase === "transcribing" && <p role="status">Transcribing…</p>}
          {phase === "confirmed" && (
            <>
              <p className="wizard-success-text">Heard: "{transcript || "…"}"</p>
              <p>Now let's check your speakers — you should hear a short tone.</p>
              <audio controls src="/assets/speaker-test-tone.mp3" />
            </>
          )}
        </>
      )}

      <div className="wizard-step__actions">
        <button
          type="button"
          className="wizard-btn wizard-btn--primary"
          onClick={onNext}
          disabled={!state.micTested && !error}
        >
          Continue
        </button>
        {onSkip && (
          <button type="button" className="wizard__link-btn" onClick={onSkip}>
            Skip for now
          </button>
        )}
      </div>
    </div>
  );
}
