import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { Achievement } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

/** Call this imperatively (e.g. from the session-completion flow) with
 * whatever `new_achievements` came back from `on_session_completed` on
 * the backend, to show the confetti/glow unlock moment. */
export function AchievementUnlockToast({ achievement, onDone }: { achievement: Achievement; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 40, scale: 0.8 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.9 }}
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        background: "var(--color-bg-elevated)",
        border: "1px solid var(--color-accent-primary)",
        boxShadow: "var(--shadow-glow)",
        borderRadius: "var(--radius-lg)",
        padding: "var(--space-4) var(--space-6)",
        display: "flex",
        alignItems: "center",
        gap: 12,
        zIndex: 1000,
      }}
    >
      <motion.span
        animate={{ rotate: [0, -10, 10, -6, 0], scale: [1, 1.3, 1] }}
        transition={{ duration: 0.6 }}
        style={{ fontSize: 32 }}
      >
        {achievement.icon}
      </motion.span>
      <div>
        <div style={{ fontSize: 11, color: "var(--color-accent-primary)", fontWeight: 700, textTransform: "uppercase" }}>
          Achievement unlocked
        </div>
        <div style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{achievement.name}</div>
        <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>{achievement.desc}</div>
      </div>
    </motion.div>
  );
}

export function AchievementShowcase() {
  const [achievements, setAchievements] = useState<Achievement[] | null>(null);

  useEffect(() => {
    motivationApi.listAchievements().then(setAchievements).catch(() => setAchievements([]));
  }, []);

  if (!achievements) return null;

  const unlocked = achievements.filter((a) => a.unlocked);

  return (
    <div className="mv-card">
      <p className="mv-card-title">
        🏆 Achievements ({unlocked.length}/{achievements.length})
      </p>
      <div className="mv-achievement-grid">
        <AnimatePresence>
          {achievements.map((a) => (
            <motion.div
              key={a.id}
              className="mv-achievement-badge"
              data-locked={!a.unlocked}
              layout
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              title={a.desc}
            >
              <span className="mv-achievement-icon">{a.icon}</span>
              <span className="mv-achievement-name">{a.name}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
