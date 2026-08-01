// frontend/src/components/wizard/steps/QuickDemoStep.tsx
//
// Merge notes: launches a 60-second, 2-question mini interview using the
// Phase 4 session state machine in a "demo" mode (bundled tiny local model,
// per Master Plan decision #1 — no API key needed to prove the app works).
// Replace `runDemoSession` with the real Phase 4 entry point, e.g.
// `sessionMachine.send({ type: "START_DEMO" })`.
import { useEffect, useState } from "react";
import type { StepProps } from "../FirstRunWizard";
import { invokeSidecar } from "../../../lib/api";

interface DemoReport {
  questionsAnswered: number;
  overallImpression: string;
}

async function runDemoSession(onProgress: (q: number) => void): Promise<DemoReport> {
  onProgress(1);
  await invokeSidecar("POST", "/interview/demo/start");
  await new Promise((r) => setTimeout(r, 1500));
  onProgress(2);
  await new Promise((r) => setTimeout(r, 1500));
  return invokeSidecar<DemoReport>("GET", "/interview/demo/report");
}

export function QuickDemoStep({ state, setState, onNext, onSkip }: StepProps) {
  const [question, setQuestion] = useState(0);
  const [report, setReport] = useState<DemoReport | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (state.demoCompleted) return;
  }, [state.demoCompleted]);

  const start = async () => {
    setRunning(true);
    try {
      const result = await runDemoSession(setQuestion);
      setReport(result);
      setState((s) => ({ ...s, demoCompleted: true }));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="wizard-step wizard-step--centered">
      <h1>Quick demo</h1>
      <p className="wizard-step__subtitle">
        A 60-second mini interview — two questions — so you can see a report before your first real
        session.
      </p>

      {!report && !running && (
        <button type="button" className="wizard-btn wizard-btn--primary" onClick={start}>
          Start demo
        </button>
      )}

      {running && !report && (
        <p role="status">Question {question} of 2…</p>
      )}

      {report && (
        <div className="wizard-demo-report">
          <p className="wizard-success-text">Demo complete — {report.questionsAnswered} questions answered.</p>
          <p>{report.overallImpression}</p>
        </div>
      )}

      <div className="wizard-step__actions">
        <button
          type="button"
          className="wizard-btn wizard-btn--primary"
          onClick={onNext}
          disabled={!state.demoCompleted}
        >
          Continue
        </button>
        {onSkip && (
          <button type="button" className="wizard__link-btn" onClick={onSkip}>
            Skip demo
          </button>
        )}
      </div>
    </div>
  );
}
