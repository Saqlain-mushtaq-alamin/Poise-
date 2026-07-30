import type { ReadinessVerdict } from "../../types/scoring";
import "./scoring.css";

interface Props {
  verdict: ReadinessVerdict;
}

const VERDICT_LABEL: Record<ReadinessVerdict["verdict"], string> = {
  ready: "Ready",
  almost_ready: "Almost ready",
  not_ready: "Not yet ready",
  insufficient_data: "Not enough data yet",
};

export function ReadinessVerdictCard({ verdict }: Props) {
  return (
    <div className={`scoring-readiness scoring-readiness--${verdict.verdict}`}>
      <div className="scoring-readiness__header">
        <span className="scoring-readiness__badge">{VERDICT_LABEL[verdict.verdict]}</span>
        {verdict.verdict !== "insufficient_data" && (
          <span className="scoring-readiness__confidence">{Math.round(verdict.confidence * 100)}% confidence</span>
        )}
      </div>
      <p className="scoring-readiness__recommendation">{verdict.recommendation}</p>
      <ul className="scoring-readiness__evidence">
        {verdict.evidence.map((e) => <li key={e}>{e}</li>)}
      </ul>
    </div>
  );
}
