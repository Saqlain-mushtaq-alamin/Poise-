import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { AnxietyExercise } from "../../../../contracts/types/motivation";
import { motivationApi } from "../../lib/motivationApi";
import "./motivation.css";

function useCountdown(totalSeconds: number, active: boolean) {
  const [remaining, setRemaining] = useState(totalSeconds);

  useEffect(() => {
    setRemaining(totalSeconds);
  }, [totalSeconds]);

  useEffect(() => {
    if (!active || remaining <= 0) return;
    const id = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(id);
  }, [active, remaining]);

  return remaining;
}

function BreathingExercise({ exercise }: { exercise: AnxietyExercise }) {
  const [running, setRunning] = useState(false);
  const pattern = exercise.pattern ?? { inhale: 4, hold: 7, exhale: 8, cycles: 3 };
  const remaining = useCountdown(exercise.duration_seconds, running);
  const cycleLength = pattern.inhale + pattern.hold + pattern.exhale;
  const elapsed = exercise.duration_seconds - remaining;
  const posInCycle = elapsed % cycleLength;

  const phase =
    posInCycle < pattern.inhale ? "inhale" : posInCycle < pattern.inhale + pattern.hold ? "hold" : "exhale";
  const scale = phase === "inhale" ? 1.5 : phase === "hold" ? 1.5 : 1;

  return (
    <div style={{ textAlign: "center" }}>
      <motion.div
        className="mv-breathing-circle"
        animate={{ scale }}
        transition={{ duration: phase === "hold" ? 0.2 : pattern[phase === "inhale" ? "inhale" : "exhale"], ease: "easeInOut" }}
      />
      <div style={{ fontSize: 18, fontWeight: 600, color: "var(--color-text-primary)", textTransform: "capitalize" }}>
        {running ? phase : "Ready"}
      </div>
      <div style={{ color: "var(--color-text-muted)", fontSize: 13, marginBottom: "var(--space-4)" }}>
        {running ? `${remaining}s remaining` : `${pattern.cycles} cycles · ${exercise.duration_seconds}s total`}
      </div>
      <button className="mv-exercise-tile" onClick={() => setRunning((r) => !r)} style={{ display: "inline-block" }}>
        {running ? "Pause" : remaining === 0 ? "Restart" : "Start breathing"}
      </button>
    </div>
  );
}

function TimerExercise({ exercise, instructions }: { exercise: AnxietyExercise; instructions: string }) {
  const [running, setRunning] = useState(false);
  const remaining = useCountdown(exercise.duration_seconds, running);
  const pct = 1 - remaining / exercise.duration_seconds;

  return (
    <div style={{ textAlign: "center" }}>
      <p style={{ color: "var(--color-text-primary)", marginBottom: "var(--space-4)" }}>{instructions}</p>
      <div className="mv-progress-track" style={{ marginBottom: "var(--space-4)" }}>
        <div className="mv-progress-fill" style={{ width: `${pct * 100}%` }} />
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text-primary)" }}>
        {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}
      </div>
      <button
        className="mv-exercise-tile"
        onClick={() => setRunning((r) => !r)}
        style={{ display: "inline-block", marginTop: "var(--space-4)" }}
      >
        {running ? "Pause" : remaining === 0 ? "Restart" : "Start"}
      </button>
    </div>
  );
}

function ExerciseDetail({ exercise }: { exercise: AnxietyExercise }) {
  switch (exercise.type) {
    case "breathing":
      return <BreathingExercise exercise={exercise} />;
    case "body":
      return <TimerExercise exercise={exercise} instructions="Stand tall, hands on hips, chin up. Hold the pose." />;
    case "mental":
      return (
        <TimerExercise
          exercise={exercise}
          instructions="Close your eyes. Imagine walking into the interview room, calm and prepared, answering with confidence."
        />
      );
    case "vocal":
      return (
        <div>
          <p style={{ color: "var(--color-text-primary)", lineHeight: 1.7 }}>{exercise.warmup_text}</p>
          <TimerExercise exercise={exercise} instructions="Read the passage above aloud at a comfortable pace." />
        </div>
      );
    case "cognitive":
      return (
        <div style={{ textAlign: "center", padding: "var(--space-6) 0" }}>
          <p style={{ fontSize: 18, color: "var(--color-text-primary)", fontWeight: 500 }}>
            {exercise.message ?? "You've prepared for this."}
          </p>
        </div>
      );
    default:
      return null;
  }
}

export function AnxietyToolkit() {
  const [exercises, setExercises] = useState<AnxietyExercise[] | null>(null);
  const [selected, setSelected] = useState<AnxietyExercise | null>(null);

  useEffect(() => {
    motivationApi.getAnxietyToolkit().then((r) => setExercises(r.exercises)).catch(() => setExercises([]));
  }, []);

  const grid = useMemo(
    () => (
      <div className="mv-exercise-grid">
        {(exercises ?? []).map((ex) => (
          <button key={ex.id} className="mv-exercise-tile" onClick={() => setSelected(ex)}>
            <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 4 }}>
              {Math.round(ex.duration_seconds / 60) || 1} min
            </div>
            <div style={{ fontWeight: 600 }}>{ex.name}</div>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 4 }}>{ex.description}</div>
          </button>
        ))}
      </div>
    ),
    [exercises]
  );

  return (
    <div className="mv-card">
      <p className="mv-card-title">🧘 Pre-interview prep</p>
      {selected ? (
        <div>
          <button
            onClick={() => setSelected(null)}
            style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", marginBottom: "var(--space-4)" }}
          >
            ← Back to all exercises
          </button>
          <ExerciseDetail exercise={selected} />
        </div>
      ) : (
        grid
      )}
    </div>
  );
}
