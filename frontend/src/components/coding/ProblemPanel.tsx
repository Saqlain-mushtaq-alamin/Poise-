/**
 * ProblemPanel — Phase 6.
 *
 * Mount point: frontend/src/components/coding/ProblemPanel.tsx
 *
 * Renders the problem statement (markdown), examples, constraints,
 * and a progressive hint reveal. Uses whatever markdown renderer the
 * rest of the app already depends on; falls back to a minimal inline
 * renderer if none is present yet so this component has no hard
 * dependency of its own.
 */
import { useState } from 'react';
import type { CodingProblem } from '../../../../contracts/types/coding';

export interface ProblemPanelProps {
  problem: CodingProblem;
  onShareClick?: () => void;
}

export function ProblemPanel({ problem, onShareClick }: ProblemPanelProps) {
  const [hintsRevealed, setHintsRevealed] = useState(0);

  return (
    <div className="poise-problem-panel">
      <div className="poise-problem-panel__header">
        <h2>{problem.title}</h2>
        <span
          className={`poise-badge poise-badge--${problem.difficulty}`}
        >
          {problem.difficulty}
        </span>
      </div>

      <div className="poise-problem-panel__topics">
        {problem.topics.map((t) => (
          <span key={t} className="poise-chip">
            {t}
          </span>
        ))}
      </div>

      <div className="poise-problem-panel__description">
        <SimpleMarkdown text={problem.description} />
      </div>

      {problem.examples.map((ex, i) => (
        <div key={i} className="poise-problem-panel__example">
          <strong>Example {i + 1}:</strong>
          <pre>Input: {ex.input}</pre>
          <pre>Output: {ex.output}</pre>
          {ex.explanation && <p>{ex.explanation}</p>}
        </div>
      ))}

      {problem.constraints.length > 0 && (
        <div className="poise-problem-panel__constraints">
          <strong>Constraints:</strong>
          <ul>
            {problem.constraints.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="poise-problem-panel__footer">
        <button
          className="poise-btn poise-btn--ghost"
          onClick={() => setHintsRevealed((n) => Math.min(n + 1, problem.hints.length))}
          disabled={hintsRevealed >= problem.hints.length}
        >
          💡 Hint {hintsRevealed > 0 ? `(${hintsRevealed}/${problem.hints.length})` : ''}
        </button>
        {onShareClick && (
          <button className="poise-btn poise-btn--ghost" onClick={onShareClick}>
            📋 Share
          </button>
        )}
      </div>

      {hintsRevealed > 0 && (
        <ul className="poise-problem-panel__hints">
          {problem.hints.slice(0, hintsRevealed).map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Minimal, dependency-free markdown-ish renderer for problem descriptions.
 * Replace with the app's real markdown component if one already exists
 * (e.g. react-markdown used elsewhere in the app). */
function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  return (
    <>
      {lines.map((line, i) => {
        if (line.startsWith('## ')) return <h3 key={i}>{line.slice(3)}</h3>;
        if (line.startsWith('# ')) return <h2 key={i}>{line.slice(2)}</h2>;
        if (line.trim() === '') return <br key={i} />;
        return <p key={i}>{line}</p>;
      })}
    </>
  );
}
