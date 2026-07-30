import type { PronunciationAnalysis, WordPronunciationScore } from "../../types/ielts";
import "./ielts.css";

interface Props {
  analysis: PronunciationAnalysis;
}

function colorClassFor(score: number): string {
  if (score >= 0.75) return "ielts-heatmap__word--good";
  if (score >= 0.5) return "ielts-heatmap__word--fair";
  return "ielts-heatmap__word--poor";
}

export function PronunciationHeatmap({ analysis }: Props) {
  return (
    <div className="ielts-heatmap">
      <div className="ielts-heatmap__words">
        {analysis.word_scores.map((ws: WordPronunciationScore, i) => (
          <span
            key={`${ws.word}-${i}`}
            className={`ielts-heatmap__word ${colorClassFor(ws.score)}`}
            title={`${ws.word}: ${(ws.score * 100).toFixed(0)}%${
              ws.problem_phonemes.length ? ` — watch: ${ws.problem_phonemes.join(", ")}` : ""
            }`}
          >
            {ws.word}
          </span>
        ))}
      </div>

      {analysis.problem_sounds.length > 0 && (
        <div className="ielts-heatmap__problem-sounds">
          <span className="ielts-heatmap__problem-sounds-label">Recurring sounds to practice:</span>
          {analysis.problem_sounds.slice(0, 6).map((s) => (
            <span key={s} className="ielts-heatmap__phoneme-chip">{s}</span>
          ))}
        </div>
      )}

      <p className="ielts-heatmap__caveat">{analysis.confidence_caveat}</p>
    </div>
  );
}
