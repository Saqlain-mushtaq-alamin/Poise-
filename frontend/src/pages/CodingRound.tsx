/**
 * CodingRound — Phase 6.
 *
 * Mount point: frontend/src/pages/CodingRound.tsx (or
 * frontend/src/components/coding/CodingRound.tsx if your app treats
 * it as an embedded component rather than a routed page — Phase 4's
 * conductor renders this when `InterviewSection.type === "coding"`).
 *
 * Split-view layout: problem (left) + editor/output (right), matching
 * the ASCII mock in 06-coding-sandbox.md §6.6.
 *
 * Emits `coding-round-complete` (CustomEvent) with the CodeEvaluation
 * payload when the round finishes, per the Phase 4 handoff contract:
 * "The coding round emits `coding-round-complete` with the CodeEvaluation."
 */
import { useEffect, useState } from 'react';
import { CodeEditor } from '../components/coding/CodeEditor';
import { OutputPanel } from '../components/coding/OutputPanel';
import { ProblemPanel } from '../components/coding/ProblemPanel';
import { ScreenCaptureButton } from '../components/coding/ScreenCapture';
import { CodingAPI } from '../lib/codingApi';
import '../components/coding/coding.css';
import type {
  CodeEvaluation,
  ExecutionResult,
  Language,
} from '../../../contracts/types/coding';

export interface CodingRoundProps {
  sessionId: string;
  codingApi: CodingAPI;
  difficulty?: string;
  topics?: string[];
  onComplete?: (evaluation: CodeEvaluation) => void;
}

const CODING_ROUND_COMPLETE_EVENT = 'coding-round-complete';

export function CodingRound({
  sessionId,
  codingApi,
  difficulty = 'medium',
  topics = [],
  onComplete,
}: CodingRoundProps) {
  const [roundId, setRoundId] = useState<string | null>(null);
  const [problem, setProblem] = useState<Awaited<ReturnType<CodingAPI['generateProblem']>> | null>(
    null
  );
  const [language, setLanguage] = useState<Language>('python');
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [_lastCode, setLastCode] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Try the full session-based round start first
        const res = await codingApi.startCodingRound(sessionId, { difficulty, topics });
        if (cancelled) return;
        setRoundId(res.round_id);
        setProblem(res.problem);
      } catch {
        // Backend coding-round endpoint not available — fall back to standalone
        // problem generation so the sandbox still works mid-interview.
        try {
          const fallbackProblem = await codingApi.generateProblem({ difficulty, topics });
          if (cancelled) return;
          // Use a local round id so submit/finalize is a no-op
          setRoundId(`local-${Date.now()}`);
          setProblem(fallbackProblem);
        } catch (e2) {
          if (!cancelled) setError('Could not load a coding problem. Please retry.');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, difficulty, topics, codingApi]);

  const handleRun = async (code: string) => {
    if (!problem?.id) return;
    setIsRunning(true);
    setError(null);
    setLastCode(code);
    try {
      const result = await codingApi.execute({
        code,
        language,
        problem_id: problem.id,
      });
      setExecutionResult(result);
    } catch (e) {
      setError('Execution failed. Please try again.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmit = async (code: string) => {
    if (!problem?.id || !roundId) return;
    setIsSubmitting(true);
    setError(null);
    setLastCode(code);
    try {
      const execution = await codingApi.execute({ code, language, problem_id: problem.id });
      setExecutionResult(execution);
      await codingApi.evaluate(code, language, problem.id, execution);
      // Submission is now the current best on the backend; finalize the round.
      await finalizeRound();
    } catch (e) {
      setError('Submission failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const finalizeRound = async () => {
    if (!roundId) return;
    setIsFinalizing(true);
    try {
      // Local fallback rounds (no real backend round) — just close the sandbox
      if (roundId.startsWith('local-')) {
        onComplete?.(null as unknown as CodeEvaluation);
        window.dispatchEvent(new CustomEvent(CODING_ROUND_COMPLETE_EVENT, { detail: null }));
        return;
      }
      const result = await codingApi.completeCodingRound(sessionId, roundId);
      onComplete?.(result.final_evaluation);
      window.dispatchEvent(
        new CustomEvent(CODING_ROUND_COMPLETE_EVENT, { detail: result })
      );
    } catch {
      // Finalize failed — close the sandbox gracefully anyway
      onComplete?.(null as unknown as CodeEvaluation);
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleScreenshotCapture = async (blob: Blob) => {
    try {
      await codingApi.evaluateScreenshot(blob, `Coding round: ${problem?.title ?? ''}`, sessionId);
    } catch {
      setError('Screenshot analysis failed, continuing without it.');
    }
  };

  if (error && !problem) {
    return <div className="poise-coding-round__error">{error}</div>;
  }

  if (!problem) {
    return <div className="poise-coding-round__loading">Generating your coding problem…</div>;
  }

  return (
    <div className="poise-coding-round">
      <div className="poise-coding-round__left">
        <ProblemPanel problem={problem} />
        <ScreenCaptureButton onCapture={handleScreenshotCapture} disabled={isFinalizing} />
      </div>

      <div className="poise-coding-round__right">
        <div className="poise-coding-round__editor">
          <CodeEditor
            language={language}
            onLanguageChange={setLanguage}
            starterCode={problem.starter_code}
            testCases={problem.test_cases}
            onRun={handleRun}
            onSubmit={handleSubmit}
            isRunning={isRunning}
            isSubmitting={isSubmitting || isFinalizing}
          />
        </div>
        <div className="poise-coding-round__output">
          <OutputPanel result={executionResult} isLoading={isRunning} />
        </div>
      </div>

      {error && <div className="poise-coding-round__toast">{error}</div>}
    </div>
  );
}
