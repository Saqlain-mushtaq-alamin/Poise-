import "./scoring.css";

interface Axis {
  label: string;
  value: number;   // 0-100
  available?: boolean;
}

interface Props {
  axes: Axis[];
  size?: number;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

export function RadarChart({ axes, size = 280 }: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 48;
  const step = 360 / Math.max(1, axes.length);
  const rings = [0.25, 0.5, 0.75, 1];

  const points = axes.map((a, i) => polarToCartesian(cx, cy, (Math.max(0, a.value) / 100) * r, i * step));
  const polygon = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="scoring-radar" role="img" aria-label="Score by dimension">
      {rings.map((ratio) => (
        <polygon
          key={ratio}
          className="scoring-radar__ring"
          points={axes.map((_, i) => { const p = polarToCartesian(cx, cy, ratio * r, i * step); return `${p.x},${p.y}`; }).join(" ")}
        />
      ))}
      {axes.map((a, i) => {
        const outer = polarToCartesian(cx, cy, r, i * step);
        const labelPt = polarToCartesian(cx, cy, r + 28, i * step);
        return (
          <g key={a.label}>
            <line x1={cx} y1={cy} x2={outer.x} y2={outer.y} className="scoring-radar__axis" />
            <text x={labelPt.x} y={labelPt.y} className="scoring-radar__axis-label" textAnchor="middle">{a.label}</text>
            <text x={labelPt.x} y={labelPt.y + 14} className="scoring-radar__axis-value" textAnchor="middle">
              {a.available === false ? "N/A" : Math.round(a.value)}
            </text>
          </g>
        );
      })}
      <polygon points={polygon} className="scoring-radar__shape" />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3.5} className="scoring-radar__point" />
      ))}
    </svg>
  );
}
