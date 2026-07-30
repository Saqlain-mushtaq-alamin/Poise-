import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { CoachSummary } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

const TREND_ICON: Record<CoachSummary["score_trend"], string> = {
  improving: "📈",
  stable: "➡️",
  declining: "📉",
  no_data: "🌱",
};

export function CoachSummaryCard() {
  const [summary, setSummary] = useState<CoachSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    motivationApi
      .getWeeklySummary()
      .then(setSummary)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="mv-card">
        <p className="mv-card-title">Weekly coach summary</p>
        <div className="mv-empty-state">Putting your week together…</div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <motion.div className="mv-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <p className="mv-card-title">
        {TREND_ICON[summary.score_trend]} Week of {summary.week_start}
      </p>
      <p className="mv-coach-narrative">{summary.narrative}</p>
      <div style={{ display: "flex", gap: "var(--space-6)", marginTop: "var(--space-4)", fontSize: 13 }}>
        <span style={{ color: "var(--color-text-secondary)" }}>
          {summary.sessions_count} session{summary.sessions_count === 1 ? "" : "s"}
        </span>
        <span style={{ color: "var(--color-text-secondary)" }}>
          {summary.practice_time_hours.toFixed(1)}h practice
        </span>
      </div>
      {summary.focus_areas.length > 0 && (
        <div className="mv-coach-tags">
          {summary.focus_areas.map((f) => (
            <span key={f} className="mv-tag">
              🎯 {f}
            </span>
          ))}
        </div>
      )}
      {summary.celebration.length > 0 && (
        <div className="mv-coach-tags">
          {summary.celebration.map((c) => (
            <span key={c} className="mv-tag" style={{ color: "var(--color-accent-success)" }}>
              ✓ {c}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}
