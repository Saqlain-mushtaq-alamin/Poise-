import { useState } from "react";
import type { ReplayData } from "../../types/scoring";
import "../scoring/scoring.css";

interface Props {
  replay: ReplayData;
}

export function SessionReplay({ replay }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const totalSeconds = Math.max(1, replay.duration_minutes * 60);

  return (
    <div className="replay-timeline">
      <div className="replay-timeline__track">
        {replay.events.map((e, i) => (
          <button
            key={i}
            className={`replay-timeline__marker replay-timeline__marker--${e.kind} ${selected === i ? "replay-timeline__marker--selected" : ""}`}
            style={{ left: `${(e.timestamp_s / totalSeconds) * 100}%` }}
            onClick={() => setSelected(i)}
            title={e.label}
          />
        ))}
      </div>
      {selected !== null && replay.events[selected] && (
        <div className="replay-timeline__detail">
          <span className="replay-timeline__detail-time">
            {Math.floor(replay.events[selected].timestamp_s / 60)}:{String(Math.floor(replay.events[selected].timestamp_s % 60)).padStart(2, "0")}
          </span>
          <strong>{replay.events[selected].label}</strong>
          {replay.events[selected].detail && <p>{replay.events[selected].detail}</p>}
        </div>
      )}
    </div>
  );
}
