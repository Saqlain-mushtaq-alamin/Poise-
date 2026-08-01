import { useState } from "react";
import { ReadinessVerdictCard } from "../components/scoring/ReadinessVerdictCard";
import { TrendLineChart } from "../components/scoring/TrendLineChart";
import { useTrends } from "../hooks/useTrends";
import "../components/scoring/scoring.css";

export default function Analytics() {
  const [mode, setMode] = useState<string | undefined>(undefined);
  const { trends, readiness, loading } = useTrends(mode);

  if (loading) return <div className="scoring-page">Loading…</div>;

  return (
    <div className="scoring-page">
      <h1>Progress & Analytics</h1>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button onClick={() => setMode(undefined)} disabled={mode === undefined}>All</button>
        <button onClick={() => setMode("interview")} disabled={mode === "interview"}>Interview</button>
        <button onClick={() => setMode("ielts")} disabled={mode === "ielts"}>IELTS</button>
      </div>

      {readiness && (
        <section>
          <h2>Are you ready?</h2>
          <ReadinessVerdictCard verdict={readiness} />
        </section>
      )}

      {trends && (
        <section>
          <h2>Score trend ({trends.overall_trend})</h2>
          <TrendLineChart points={trends.points} />
        </section>
      )}

      {trends && Object.keys(trends.dimension_averages).length > 0 && (
        <section>
          <h2>Average by dimension</h2>
          <div className="scoring-dimensions">
            {Object.entries(trends.dimension_averages).map(([name, avg]) => (
              <div key={name} className="scoring-dimension">
                <span>{name}</span>
                <span className="scoring-dimension__score">{avg.toFixed(0)}/100</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
