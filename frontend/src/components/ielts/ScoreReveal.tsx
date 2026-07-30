import { AnimatePresence, motion, useMotionValue, useTransform, animate } from "framer-motion";
import { useEffect, useState } from "react";
import type { IELTSBandScore, BandDetail } from "../../types/ielts";
import { RadarChart } from "./RadarChart";
import "./ielts.css";

interface Props {
  score: IELTSBandScore;
}

function useCountUp(target: number, durationS = 1.4) {
  const value = useMotionValue(0);
  const rounded = useTransform(value, (v) => v.toFixed(1));
  useEffect(() => {
    const controls = animate(value, target, { duration: durationS, ease: [0.16, 1, 0.3, 1] });
    return () => controls.stop();
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps
  return rounded;
}

const CRITERIA: { key: keyof IELTSBandScore; label: string; short: string }[] = [
  { key: "fluency_and_coherence", label: "Fluency & Coherence", short: "FC" },
  { key: "lexical_resource", label: "Lexical Resource", short: "LR" },
  { key: "grammatical_range_accuracy", label: "Grammatical Range & Accuracy", short: "GRA" },
  { key: "pronunciation", label: "Pronunciation", short: "P" },
];

function CriterionRow({ label, detail }: { label: string; detail: BandDetail }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="ielts-score-reveal__criterion">
      <button
        className="ielts-score-reveal__criterion-header"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span>{label}</span>
        <span className="ielts-score-reveal__criterion-band">{detail.band.toFixed(1)}</span>
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="ielts-score-reveal__criterion-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <p>{detail.justification}</p>
            {detail.strengths.length > 0 && (
              <div className="ielts-score-reveal__list ielts-score-reveal__list--strengths">
                <strong>Strengths</strong>
                <ul>{detail.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
            )}
            {detail.areas_to_improve.length > 0 && (
              <div className="ielts-score-reveal__list ielts-score-reveal__list--improve">
                <strong>Areas to improve</strong>
                <ul>{detail.areas_to_improve.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
            )}
            {detail.example_from_response && (
              <p className="ielts-score-reveal__example">"{detail.example_from_response}"</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ScoreReveal({ score }: Props) {
  const overall = useCountUp(score.overall_band);

  return (
    <motion.div
      className="ielts-score-reveal"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      <div className="ielts-score-reveal__hero">
        <span className="ielts-score-reveal__hero-label">Overall Band Score</span>
        <motion.span className="ielts-score-reveal__hero-value">{overall}</motion.span>
      </div>

      <RadarChart
        axes={CRITERIA.map((c) => ({ label: c.short, value: (score[c.key] as BandDetail).band }))}
      />

      <div className="ielts-score-reveal__criteria">
        {CRITERIA.map((c) => (
          <CriterionRow key={c.key} label={c.label} detail={score[c.key] as BandDetail} />
        ))}
      </div>
    </motion.div>
  );
}
