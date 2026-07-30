import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { ReflectionAnswer, ReflectionPrompt } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

/**
 * Render this BEFORE the SessionReport route/component. Only call
 * `onComplete` (which should navigate to the report) after submission —
 * reflecting before seeing scores is the entire point (see 10.11).
 */
export function SelfReflection({
  sessionId,
  onComplete,
}: {
  sessionId: string;
  onComplete: (selfRating: number | null) => void;
}) {
  const [prompts, setPrompts] = useState<ReflectionPrompt[] | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, ReflectionAnswer>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    motivationApi.getReflectionPrompts().then(setPrompts).catch(() => setPrompts([]));
  }, []);

  if (!prompts) return null;
  const current = prompts[index];
  const isRatingPrompt = current.prompt_id === "rate_before_report";
  const isLast = index === prompts.length - 1;

  function setAnswer(patch: Partial<ReflectionAnswer>) {
    setAnswers((prev) => ({
      ...prev,
      [current.prompt_id]: { ...prev[current.prompt_id], prompt_id: current.prompt_id, ...patch },
    }));
  }

  async function handleNext() {
    if (!isLast) {
      setIndex((i) => i + 1);
      return;
    }
    setSubmitting(true);
    try {
      const result = await motivationApi.submitReflection({
        session_id: sessionId,
        answers: Object.values(answers),
      });
      onComplete(result.self_rating);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mv-card" style={{ maxWidth: 520, margin: "0 auto" }}>
      <p className="mv-card-title">
        Before your report ({index + 1}/{prompts.length})
      </p>
      <AnimatePresence mode="wait">
        <motion.div
          key={current.prompt_id}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          transition={{ duration: 0.18 }}
        >
          <p className="mv-reflection-prompt">{current.prompt}</p>

          {isRatingPrompt ? (
            <div className="mv-scale-row">
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <div
                  key={n}
                  className="mv-scale-dot"
                  data-active={answers[current.prompt_id]?.self_rating === n}
                  onClick={() => setAnswer({ self_rating: n })}
                >
                  {n}
                </div>
              ))}
            </div>
          ) : (
            <textarea
              className="mv-reflection-textarea"
              placeholder="Your answer (optional)…"
              value={answers[current.prompt_id]?.response ?? ""}
              onChange={(e) => setAnswer({ response: e.target.value })}
            />
          )}
        </motion.div>
      </AnimatePresence>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "var(--space-6)" }}>
        <button
          onClick={() => onComplete(null)}
          style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}
        >
          Skip reflection
        </button>
        <button
          onClick={handleNext}
          disabled={submitting}
          style={{
            background: "var(--color-accent-primary)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius-sm)",
            padding: "8px 20px",
            cursor: "pointer",
          }}
        >
          {isLast ? (submitting ? "Submitting…" : "See my report") : "Next"}
        </button>
      </div>
    </div>
  );
}
