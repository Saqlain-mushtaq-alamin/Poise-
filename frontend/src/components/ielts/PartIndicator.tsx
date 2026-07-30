import "./ielts.css";

interface Props {
  currentPart: number | null | undefined;
}

const PARTS = [
  { n: 1, label: "Introduction" },
  { n: 2, label: "Long Turn" },
  { n: 3, label: "Discussion" },
];

export function PartIndicator({ currentPart }: Props) {
  return (
    <div className="ielts-part-indicator">
      {PARTS.map((p) => {
        const status =
          currentPart == null ? "pending" : p.n < currentPart ? "done" : p.n === currentPart ? "active" : "pending";
        return (
          <div key={p.n} className={`ielts-part-indicator__item ielts-part-indicator__item--${status}`}>
            <span className="ielts-part-indicator__badge">{status === "done" ? "✓" : p.n}</span>
            <span className="ielts-part-indicator__label">Part {p.n} — {p.label}</span>
          </div>
        );
      })}
    </div>
  );
}
