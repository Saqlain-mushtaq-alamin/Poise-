import type { ProsodyAnalysis } from "../../types/ielts";
import "./ielts.css";

interface Props {
  analysis: ProsodyAnalysis;
  durationS: number; // total response duration, for scaling the timeline
}

const PACE_LABEL: Record<ProsodyAnalysis["pace_assessment"], string> = {
  too_fast: "A little fast",
  good: "Good pace",
  too_slow: "A little slow",
};

export function ProsodyTimeline({ analysis, durationS }: Props) {
  const safeDuration = Math.max(durationS, 1);

  return (
    <div className="ielts-prosody">
      <div className="ielts-prosody__stats">
        <div className="ielts-prosody__stat">
          <span className="ielts-prosody__stat-value">{analysis.speaking_rate_wpm.toFixed(0)}</span>
          <span className="ielts-prosody__stat-label">words / min</span>
          <span className={`ielts-prosody__pace-badge ielts-prosody__pace-badge--${analysis.pace_assessment}`}>
            {PACE_LABEL[analysis.pace_assessment]}
          </span>
        </div>
        <div className="ielts-prosody__stat">
          <span className="ielts-prosody__stat-value">{(analysis.filler_ratio * 100).toFixed(1)}%</span>
          <span className="ielts-prosody__stat-label">filler words</span>
        </div>
        <div className="ielts-prosody__stat">
          <span className="ielts-prosody__stat-value">{analysis.intonation_variety.toFixed(2)}</span>
          <span className="ielts-prosody__stat-label">intonation variety</span>
        </div>
      </div>

      <div className="ielts-prosody__timeline">
        {analysis.pause_analysis.long_pauses.map((p, i) => (
          <div
            key={i}
            className="ielts-prosody__pause-marker"
            style={{
              left: `${(p.start_s / safeDuration) * 100}%`,
              width: `${Math.max(0.5, (p.duration_s / safeDuration) * 100)}%`,
            }}
            title={`Pause: ${p.duration_s.toFixed(1)}s`}
          />
        ))}
        {analysis.filler_words.map((f, i) => (
          <div
            key={i}
            className="ielts-prosody__filler-marker"
            style={{ left: `${(f.timestamp_s / safeDuration) * 100}%` }}
            title={`"${f.text}" at ${f.timestamp_s.toFixed(1)}s`}
          />
        ))}
      </div>
      <div className="ielts-prosody__legend">
        <span><i className="ielts-prosody__legend-swatch ielts-prosody__legend-swatch--pause" /> Long pause</span>
        <span><i className="ielts-prosody__legend-swatch ielts-prosody__legend-swatch--filler" /> Filler word</span>
      </div>
    </div>
  );
}
