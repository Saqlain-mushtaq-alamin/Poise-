import "./ielts.css";

interface Axis {
  label: string;
  value: number; // 0-9
}

interface Props {
  axes: Axis[];
  size?: number;
}

const MAX_BAND = 9;

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

export function RadarChart({ axes, size = 260 }: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 40;
  const step = 360 / axes.length;

  const rings = [0.25, 0.5, 0.75, 1];
  const points = axes.map((a, i) => polarToCartesian(cx, cy, (a.value / MAX_BAND) * r, i * step));
  const polygon = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="ielts-radar" role="img" aria-label="Band score by criterion">
      {rings.map((ratio) => (
        <polygon
          key={ratio}
          className="ielts-radar__ring"
          points={axes
            .map((_, i) => {
              const p = polarToCartesian(cx, cy, ratio * r, i * step);
              return `${p.x},${p.y}`;
            })
            .join(" ")}
        />
      ))}
      {axes.map((a, i) => {
        const outer = polarToCartesian(cx, cy, r, i * step);
        const labelPt = polarToCartesian(cx, cy, r + 24, i * step);
        return (
          <g key={a.label}>
            <line x1={cx} y1={cy} x2={outer.x} y2={outer.y} className="ielts-radar__axis" />
            <text x={labelPt.x} y={labelPt.y} className="ielts-radar__axis-label" textAnchor="middle">
              {a.label}
            </text>
            <text x={labelPt.x} y={labelPt.y + 14} className="ielts-radar__axis-value" textAnchor="middle">
              {a.value.toFixed(1)}
            </text>
          </g>
        );
      })}
      <polygon points={polygon} className="ielts-radar__shape" />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3.5} className="ielts-radar__point" />
      ))}
    </svg>
  );
}
