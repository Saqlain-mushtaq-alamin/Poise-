import type { AnnotatedAnswer } from "../../types/scoring";
import "./scoring.css";

interface Props {
  annotated: AnnotatedAnswer;
}

const STRUCTURE_LABEL: Record<AnnotatedAnswer["overall_structure"], string> = {
  well_structured: "Well structured",
  rambling: "Rambling",
  too_brief: "Too brief",
  unfocused: "Unfocused",
};

export function SentenceAnnotatedAnswer({ annotated }: Props) {
  const fw = annotated.framework_analysis;
  return (
    <div className="scoring-annotated">
      <div className="scoring-annotated__header">
        <span className={`scoring-annotated__structure scoring-annotated__structure--${annotated.overall_structure}`}>
          {STRUCTURE_LABEL[annotated.overall_structure]}
        </span>
        {fw.framework !== "none_detected" && (
          <span className="scoring-annotated__framework">
            {fw.framework} detected
            {[
              fw.situation_present && "S",
              fw.task_present && "T",
              fw.action_present && "A",
              fw.result_present && "R",
            ].filter(Boolean).length > 0 &&
              ` (${[fw.situation_present && "S", fw.task_present && "T", fw.action_present && "A", fw.result_present && "R"].filter(Boolean).join("-")})`}
            {fw.result_has_metric && " · quantified result"}
          </span>
        )}
      </div>
      <p className="scoring-annotated__text">
        {annotated.sentences.map((s, i) => (
          <span
            key={i}
            className={`scoring-annotated__sentence scoring-annotated__sentence--${s.highlight_color}`}
            title={s.suggestion ? `${s.reason} — Try: ${s.suggestion}` : s.reason}
          >
            {s.text}{" "}
          </span>
        ))}
      </p>
    </div>
  );
}
