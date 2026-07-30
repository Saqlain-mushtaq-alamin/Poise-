import { motion } from "framer-motion";
import type { CueCard as CueCardType } from "../../types/ielts";
import "./ielts.css";

interface Props {
  cueCard: CueCardType;
}

export function CueCard({ cueCard }: Props) {
  return (
    <motion.div
      className="ielts-cue-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
    >
      <div className="ielts-cue-card__header">
        <span className="ielts-cue-card__icon" aria-hidden>📋</span>
        <span>CUE CARD</span>
      </div>
      <h2 className="ielts-cue-card__topic">{cueCard.topic}</h2>
      <p className="ielts-cue-card__prompt">You should say:</p>
      <ul className="ielts-cue-card__bullets">
        {cueCard.bullets.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>
    </motion.div>
  );
}
