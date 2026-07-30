import type { AnswerDiff, ModelAnswer } from "../../types/scoring";
import "./scoring.css";

interface Props {
  modelAnswer: ModelAnswer;
  diff: AnswerDiff;
}

export function AnswerDiffView({ modelAnswer, diff }: Props) {
  if (modelAnswer.is_placeholder) {
    return <p className="scoring-diff__placeholder">{modelAnswer.full_text}</p>;
  }

  return (
    <div className="scoring-diff">
      <div className="scoring-diff__meta">
        <span>{modelAnswer.framework_used} framework</span>
        <span>{Math.round(diff.similarity_ratio * 100)}% similar to your answer</span>
      </div>
      <p className="scoring-diff__text">
        {diff.segments.map((seg, i) => (
          <span key={i} className={`scoring-diff__segment scoring-diff__segment--${seg.kind}`}>
            {seg.text}
          </span>
        ))}
      </p>
      {modelAnswer.key_elements.length > 0 && (
        <ul className="scoring-diff__key-elements">
          {modelAnswer.key_elements.map((k) => <li key={k}>{k}</li>)}
        </ul>
      )}
      {modelAnswer.why_it_works && <p className="scoring-diff__why">{modelAnswer.why_it_works}</p>}
    </div>
  );
}
