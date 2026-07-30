import { motion } from "framer-motion";
import "./ielts.css";

interface Props {
  label: string;
  remainingSeconds: number;
  totalSeconds: number;
  warnAtRatio?: number; // switch to warning color once remaining/total < this
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function PrepTimer({ label, remainingSeconds, totalSeconds, warnAtRatio = 0.25 }: Props) {
  const ratio = totalSeconds > 0 ? remainingSeconds / totalSeconds : 0;
  const isWarning = ratio <= warnAtRatio;
  const circumference = 2 * Math.PI * 42;
  const offset = circumference * (1 - ratio);

  return (
    <div className="ielts-timer">
      <svg viewBox="0 0 96 96" className="ielts-timer__ring" aria-hidden>
        <circle cx="48" cy="48" r="42" className="ielts-timer__track" />
        <motion.circle
          cx="48"
          cy="48"
          r="42"
          className={isWarning ? "ielts-timer__progress ielts-timer__progress--warn" : "ielts-timer__progress"}
          strokeDasharray={circumference}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.5, ease: "linear" }}
        />
      </svg>
      <div className="ielts-timer__label-group">
        <span className="ielts-timer__time">{formatTime(remainingSeconds)}</span>
        <span className="ielts-timer__label">{label}</span>
      </div>
    </div>
  );
}
