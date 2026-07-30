import type { CoverageMatrix } from "../../types/scoring";
import "./scoring.css";

interface Props {
  matrix: CoverageMatrix;
}

export function CoverageMatrixView({ matrix }: Props) {
  if (matrix.required_skills.length === 0) {
    return <p className="scoring-coverage__empty">Add a job description to see skill coverage.</p>;
  }

  return (
    <div className="scoring-coverage">
      <div className="scoring-coverage__summary">
        <span className="scoring-coverage__pct">{matrix.coverage_pct.toFixed(0)}%</span>
        <span className="scoring-coverage__pct-label">of JD skills covered by this session</span>
      </div>
      <ul className="scoring-coverage__list">
        {matrix.coverage.map((c) => (
          <li key={c.skill} className={`scoring-coverage__item scoring-coverage__item--${c.covered ? "covered" : "gap"}`}>
            <span className="scoring-coverage__icon">{c.covered ? "✓" : "—"}</span>
            <span className="scoring-coverage__skill">{c.skill}</span>
            {c.evidence_question && <span className="scoring-coverage__evidence">via "{c.evidence_question}"</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
