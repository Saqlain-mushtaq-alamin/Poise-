import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AchievementShowcase, AchievementUnlockToast } from "../components/motivation/AchievementShowcase";
import { CalibrationChart } from "../components/motivation/CalibrationChart";
import { CoachSummaryCard } from "../components/motivation/CoachSummaryCard";
import { GoalsSection } from "../components/motivation/GoalCard";
import { PracticeQueue } from "../components/motivation/PracticeQueue";
import { StreakHeatmap } from "../components/motivation/StreakHeatmap";
import { AnxietyToolkit } from "../components/motivation/AnxietyToolkit";
import type { Achievement } from "../../../contracts/types/motivation";
import { pollAndDeliverNotification } from "../lib/motivationApi";
import "../components/motivation/motivation.css";

/**
 * Replaces the Phase 1 placeholder Dashboard. Keeps the existing
 * "Start Interview" / "Practice IELTS" CTAs (pass them in as `actions`,
 * or wire directly to your router) and adds every Phase 10 motivation
 * signal around them, per the 10.8 wireframe.
 */
export function Dashboard({
  userName = "",
  onStartInterview,
  onStartIelts,
}: {
  userName?: string;
  onStartInterview?: () => void;
  onStartIelts?: () => void;
}) {
  const [toastAchievement, setToastAchievement] = useState<Achievement | null>(null);
  const [showAnxietyToolkit, setShowAnxietyToolkit] = useState(false);

  useEffect(() => {
    // Cap at every 5 minutes — the backend enforces the real 1/day rule,
    // this interval just controls how promptly we notice a pending one.
    const id = setInterval(pollAndDeliverNotification, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)", padding: "var(--space-6)" }}>
      <motion.h1
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ fontSize: 24, fontWeight: 700, color: "var(--color-text-primary)", margin: 0 }}
      >
        {greeting}{userName ? `, ${userName}` : ""}!
      </motion.h1>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        <StreakHeatmap />
        <GoalsSection />
      </div>

      <PracticeQueue />

      <div style={{ display: "flex", gap: "var(--space-4)" }}>
        <button
          onClick={onStartInterview}
          style={{
            flex: 1,
            padding: "var(--space-4)",
            background: "var(--color-accent-primary)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius-md)",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Start Interview →
        </button>
        <button
          onClick={onStartIelts}
          style={{
            flex: 1,
            padding: "var(--space-4)",
            background: "var(--color-accent-secondary)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius-md)",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Practice IELTS →
        </button>
        <button
          onClick={() => setShowAnxietyToolkit((v) => !v)}
          style={{
            padding: "var(--space-4)",
            background: "var(--color-surface)",
            color: "var(--color-text-primary)",
            border: "none",
            borderRadius: "var(--radius-md)",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          🧘 Pre-Interview Prep
        </button>
      </div>

      {showAnxietyToolkit && <AnxietyToolkit />}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        <CoachSummaryCard />
        <CalibrationChart />
      </div>

      <AchievementShowcase />

      {toastAchievement && (
        <AchievementUnlockToast achievement={toastAchievement} onDone={() => setToastAchievement(null)} />
      )}
    </div>
  );
}
