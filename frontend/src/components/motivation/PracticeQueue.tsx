import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { PracticeSuggestion } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

export function PracticeQueue({ onStart }: { onStart?: (s: PracticeSuggestion) => void }) {
  const [items, setItems] = useState<PracticeSuggestion[] | null>(null);

  useEffect(() => {
    motivationApi.getPracticeQueue(3).then(setItems).catch(() => setItems([]));
  }, []);

  if (!items) return null;

  return (
    <div className="mv-card">
      <p className="mv-card-title">📋 Today's practice queue</p>
      {items.length === 0 ? (
        <div className="mv-empty-state">You're all caught up — start a fresh session anytime.</div>
      ) : (
        items.map((item, i) => (
          <motion.div
            key={item.title}
            className="mv-queue-item"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i * 0.05 }}
          >
            <div>
              <div style={{ fontWeight: 600, color: "var(--color-text-primary)", fontSize: 14 }}>
                {i + 1}. {item.title}
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{item.reason}</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="mv-queue-priority" data-priority={item.priority}>
                {item.priority}
              </span>
              {onStart && (
                <button
                  onClick={() => onStart(item)}
                  style={{
                    background: "var(--color-accent-primary)",
                    color: "white",
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    padding: "6px 12px",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  Practice
                </button>
              )}
            </div>
          </motion.div>
        ))
      )}
    </div>
  );
}
