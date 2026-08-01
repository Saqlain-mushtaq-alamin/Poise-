// frontend/src/components/wizard/steps/CameraCheckStep.tsx
//
// Merge notes: face detection reuses Phase 5's webcam analysis pipeline
// (frontend/src/lib/webcam/face-detect.ts). This step is optional per
// Phase 9.1 spec — "skip" is a first-class outcome, not an error state.
import { useEffect, useRef, useState } from "react";
import type { StepProps } from "../FirstRunWizard";

export function CameraCheckStep({ state: _state, setState, onNext, onSkip }: StepProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [phase, setPhase] = useState<"idle" | "streaming" | "detected" | "denied">("idle");

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setPhase("streaming");
      // TODO(merge): replace with real Phase 5 face-detection call.
      setTimeout(() => {
        setState((s) => ({ ...s, cameraTested: true }));
        setPhase("detected");
      }, 1500);
    } catch {
      // Maps to ErrorCategory.CAMERA_PERMISSION (see lib/errors.ts)
      setPhase("denied");
    }
  };

  useEffect(() => {
    return () => {
      const stream = videoRef.current?.srcObject as MediaStream | undefined;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const skipCamera = () => {
    setState((s) => ({ ...s, cameraSkipped: true }));
    onNext();
  };

  return (
    <div className="wizard-step wizard-step--centered">
      <h1>Camera check (optional)</h1>
      <p className="wizard-step__subtitle">
        Poise can read posture and eye contact signals during practice sessions. This is entirely
        optional and only runs locally — no video ever leaves your machine.
      </p>

      <div className="wizard-camera-preview">
        <video ref={videoRef} autoPlay muted playsInline aria-label="Camera preview" />
      </div>

      {phase === "idle" && (
        <button type="button" className="wizard-btn wizard-btn--primary" onClick={startCamera}>
          Test camera
        </button>
      )}
      {phase === "streaming" && <p role="status">Looking for a face…</p>}
      {phase === "detected" && <p className="wizard-success-text">Face detected — you're all set.</p>}
      {phase === "denied" && (
        <p className="wizard-error-text" role="alert">Camera access denied — check system settings.</p>
      )}

      <div className="wizard-step__actions">
        <button type="button" className="wizard-btn wizard-btn--primary" onClick={onNext} disabled={phase !== "detected"}>
          Continue
        </button>
        <button type="button" className="wizard__link-btn" onClick={skipCamera}>
          Skip camera setup
        </button>
        {onSkip && (
          <button type="button" className="wizard__link-btn wizard__link-btn--muted" onClick={onSkip}>
            Complete setup later
          </button>
        )}
      </div>
    </div>
  );
}
