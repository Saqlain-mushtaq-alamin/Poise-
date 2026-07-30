import { useState } from "react";
import type { Playbook } from "../../types/scoring";
import "./scoring.css";

interface Props {
  playbook: Playbook & { key: string };
}

export function PlaybookCard({ playbook }: Props) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="scoring-playbook">
      <button className="scoring-playbook__header" onClick={() => setExpanded((e) => !e)} aria-expanded={expanded}>
        <span>{playbook.title}</span>
        <span className="scoring-playbook__chevron">{expanded ? "−" : "+"}</span>
      </button>
      <p className="scoring-playbook__description">{playbook.description}</p>
      {expanded && (
        <ul className="scoring-playbook__exercises">
          {playbook.exercises.map((ex) => (
            <li key={ex.name}>
              <strong>{ex.name}</strong> <span className="scoring-playbook__duration">{ex.duration_minutes} min</span>
              <p>{ex.description}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
