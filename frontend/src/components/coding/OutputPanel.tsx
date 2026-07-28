/**
 * OutputPanel — Phase 6.
 *
 * Mount point: frontend/src/components/coding/OutputPanel.tsx
 *
 * Renders stdout/stderr and per-test-case pass/fail, matching the
 * ASCII mock in 06-coding-sandbox.md §6.6.
 */
import type { ExecutionResult } from '../../../../contracts/types/coding';

export interface OutputPanelProps {
  result: ExecutionResult | null;
  isLoading?: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  accepted: 'Accepted',
  wrong_answer: 'Wrong Answer',
  runtime_error: 'Runtime Error',
  time_limit: 'Time Limit Exceeded',
  memory_limit: 'Memory Limit Exceeded',
  compile_error: 'Compile Error',
  internal_error: 'Internal Error',
};

export function OutputPanel({ result, isLoading = false }: OutputPanelProps) {
  if (isLoading) {
    return (
      <div className="poise-output-panel poise-output-panel--loading">
        <span className="poise-spinner" /> Executing…
      </div>
    );
  }

  if (!result) {
    return (
      <div className="poise-output-panel poise-output-panel--empty">
        Run your code to see output here.
      </div>
    );
  }

  const isAccepted = result.status === 'accepted';

  return (
    <div className="poise-output-panel">
      <div
        className={`poise-output-panel__status poise-output-panel__status--${
          isAccepted ? 'success' : 'error'
        }`}
      >
        {STATUS_LABEL[result.status] ?? result.status}
      </div>

      {result.test_results.length > 0 && (
        <ul className="poise-output-panel__tests">
          {result.test_results.map((tc, i) => (
            <li
              key={i}
              className={`poise-output-panel__test poise-output-panel__test--${
                tc.passed ? 'pass' : 'fail'
              }`}
            >
              <span>{tc.passed ? '✅' : '❌'}</span>
              <span>
                Test {i + 1}/{result.test_results.length}
                {tc.is_hidden ? ' (hidden)' : ''}
              </span>
              {!tc.passed && !tc.is_hidden && (
                <div className="poise-output-panel__test-detail">
                  <div>Input: {tc.input}</div>
                  <div>Expected: {tc.expected_output}</div>
                  <div>Got: {tc.actual_output || '(empty)'}</div>
                  {tc.error && <div>Error: {tc.error}</div>}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {result.stdout && (
        <pre className="poise-output-panel__raw">{result.stdout}</pre>
      )}
      {result.stderr && (
        <pre className="poise-output-panel__raw poise-output-panel__raw--error">
          {result.stderr}
        </pre>
      )}

      <div className="poise-output-panel__meta">
        Runtime: {result.execution_time_ms}ms
        {result.memory_used_mb > 0 && `, Memory: ${result.memory_used_mb.toFixed(1)}MB`}
        <span className="poise-output-panel__executor"> · {result.executor}</span>
      </div>
    </div>
  );
}
