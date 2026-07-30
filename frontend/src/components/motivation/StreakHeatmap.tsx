import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { StreakData } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

function level(count: number): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  if (count === 3) return 3;
  return 4;
}

function last90Days(): string[] {
  const days: string[] = [];
  const today = new Date();
  for (let i = 89; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

export function StreakHeatmap() {
  const [streak, setStreak] = useState<StreakData | null>(null);

  useEffect(() => {
    motivationApi.getStreak().then(setStreak).catch(() => setStreak(null));
  }, []);

  if (!streak) {
    return (
      <div className="mv-card">
        <p className="mv-card-title">Practice streak</p>
        <div className="mv-empty-state">Loading…</div>
      </div>
    );
  }

  if (streak.total_sessions === 0) {
    return (
      <div className="mv-card">
        <p className="mv-card-title">Practice streak</p>
        <div className="mv-empty-state">
          🔥 Your streak starts with session one. Practice today to light it up.
        </div>
      </div>
    );
  }

  const days = last90Days();

  return (
    <motion.div
      className="mv-card"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <p className="mv-card-title">Practice streak</p>
      <div className="mv-streak-header">
        <span className="mv-streak-flame">🔥</span>
        <span className="mv-streak-count">{streak.current_streak_days}</span>
        <span className="mv-streak-label">
          day{streak.current_streak_days === 1 ? "" : "s"} · longest {streak.longest_streak_days}
        </span>
      </div>

      <div className="mv-heatmap">
        {days.map((d) => (
          <div
            key={d}
            className="mv-heatmap-cell"
            data-level={level(streak.calendar[d] ?? 0)}
            title={`${d}: ${streak.calendar[d] ?? 0} session${(streak.calendar[d] ?? 0) === 1 ? "" : "s"}`}
          />
        ))}
      </div>

      {streak.streak_status === "at_risk" && (
        <p className="mv-streak-warning">
          Don't break your {streak.current_streak_days}-day streak — practice today!
        </p>
      )}
    </motion.div>
  );
}
