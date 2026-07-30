import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { Goal } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

const TYPE_LABEL: Record<Goal["type"], string> = {
  ielts_band: "IELTS Band",
  interview_score: "Interview Score",
  sessions_per_week: "Sessions / Week",
};

function formatValue(goal: Goal, value: number): string {
  return goal.type === "ielts_band" ? value.toFixed(1) : Math.round(value).toString();
}

function GoalCardSingle({ goal }: { goal: Goal }) {
  return (
    <motion.div
      className="mv-card"
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
    >
      <p className="mv-card-title">🎯 {TYPE_LABEL[goal.type]}</p>
      <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text-primary)" }}>
        {formatValue(goal, goal.current_value)}
        <span style={{ color: "var(--color-text-muted)", fontSize: 15 }}>
          {" "}/ {formatValue(goal, goal.target_value)}
        </span>
      </div>
      <div className="mv-progress-track">
        <div className="mv-progress-fill" style={{ width: `${Math.min(100, goal.progress_percent)}%` }} />
      </div>
      <div className="mv-goal-meta">
        <span>{goal.progress_percent.toFixed(0)}% there</span>
        <span>
          {goal.status === "achieved"
            ? "Achieved 🎉"
            : goal.projected_completion
              ? `On track for ${goal.projected_completion}`
              : "Not enough trend data yet"}
        </span>
      </div>
    </motion.div>
  );
}

export function GoalsSection() {
  const [goals, setGoals] = useState<Goal[] | null>(null);

  useEffect(() => {
    motivationApi.listGoals().then(setGoals).catch(() => setGoals([]));
  }, []);

  if (!goals) return null;

  if (goals.length === 0) {
    return (
      <div className="mv-card">
        <p className="mv-card-title">Goals</p>
        <div className="mv-empty-state">
          No goals set yet. Set a target band or score to track your progress toward it.
        </div>
      </div>
    );
  }

  return (
    <div className="mv-goal-grid">
      {goals.map((g) => (
        <GoalCardSingle key={g.id} goal={g} />
      ))}
    </div>
  );
}
