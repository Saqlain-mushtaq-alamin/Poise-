import { useState } from "react";
import { useHistory } from "../hooks/useHistory";
import "../components/scoring/scoring.css";

interface Props {
  onSelectSession: (sessionId: string) => void;
}

export function History({ onSelectSession }: Props) {
  const [mode, setMode] = useState<string | undefined>(undefined);
  const { sessions, loading } = useHistory(mode);

  return (
    <div className="scoring-page">
      <h1>Session History</h1>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button onClick={() => setMode(undefined)} disabled={mode === undefined}>All</button>
        <button onClick={() => setMode("interview")} disabled={mode === "interview"}>Interview</button>
        <button onClick={() => setMode("ielts")} disabled={mode === "ielts"}>IELTS</button>
      </div>

      {loading && <p>Loading…</p>}
      {!loading && sessions.length === 0 && <p>No sessions yet — complete a practice session to see it here.</p>}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--color-text-muted)", fontSize: "0.8rem" }}>
            <th>Date</th><th>Mode</th><th>Score</th><th>Duration</th><th></th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id} style={{ borderTop: "1px solid var(--color-surface)" }}>
              <td>{new Date(s.generated_at).toLocaleDateString()}</td>
              <td style={{ textTransform: "capitalize" }}>{s.mode}</td>
              <td>{s.overall_score.toFixed(0)}/100</td>
              <td>{s.duration_minutes.toFixed(0)} min</td>
              <td><button onClick={() => onSelectSession(s.session_id)}>View report</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default History;
