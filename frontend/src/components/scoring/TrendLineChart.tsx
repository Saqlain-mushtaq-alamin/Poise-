import type { TrendPoint } from "../../types/scoring";
import "./scoring.css";

interface Props {
  points: TrendPoint[];
  width?: number;
  height?: number;
}

export function TrendLineChart({ points, width = 640, height = 220 }: Props) {
  if (points.length === 0) return <p className="scoring-trend__empty">No sessions yet.</p>;

  const padding = 32;
  const xs = points.map((_, i) => padding + (i / Math.max(1, points.length - 1)) * (width - padding * 2));
  const ys = points.map((p) => height - padding - (p.overall_score / 100) * (height - padding * 2));
  const path = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="scoring-trend" role="img" aria-label="Score trend over time">
      {[0, 25, 50, 75, 100].map((v) => {
        const y = height - padding - (v / 100) * (height - padding * 2);
        return (
          <g key={v}>
            <line x1={padding} y1={y} x2={width - padding} y2={y} className="scoring-trend__gridline" />
            <text x={4} y={y + 4} className="scoring-trend__axis-label">{v}</text>
          </g>
        );
      })}
      <path d={path} className="scoring-trend__line" fill="none" />
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r={4} className="scoring-trend__point">
          <title>{`${new Date(points[i].generated_at).toLocaleDateString()}: ${points[i].overall_score.toFixed(0)}`}</title>
        </circle>
      ))}
    </svg>
  );
}
