import { useState } from "react";
import { AnswerDiffView } from "../components/scoring/AnswerDiffView";
import { CoverageMatrixView } from "../components/scoring/CoverageMatrixView";
import { DebriefChat } from "../components/scoring/DebriefChat";
import { PlaybookCard } from "../components/scoring/PlaybookCard";
import { RadarChart } from "../components/scoring/RadarChart";
import { SentenceAnnotatedAnswer } from "../components/scoring/SentenceAnnotatedAnswer";
import { SessionReplay } from "../components/replay/SessionReplay";
import { useSessionReport } from "../hooks/useSessionReport";
import { scoringApi } from "../lib/scoringApi";
import type { CoverageMatrix, ModelAnswerResponse, Playbook, ReplayData } from "../types/scoring";
import "../components/scoring/scoring.css";

interface Props {
  sessionId: string;
}

export default function SessionReport({ sessionId }: Props) {
  const { report, loading, error, refresh } = useSessionReport(sessionId);

  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [coverage, setCoverage] = useState<CoverageMatrix | null>(null);
  const [jdText, setJdText] = useState("");
  const [playbooks, setPlaybooks] = useState<(Playbook & { key: string })[] | null>(null);
  const [modelAnswers, setModelAnswers] = useState<Record<number, ModelAnswerResponse>>({});
  const [showReplay, setShowReplay] = useState(false);
  const [showDebrief, setShowDebrief] = useState(false);

  if (loading) return <div className="scoring-page">Loading report…</div>;
  if (error || !report) return <div className="scoring-page">Couldn't load this report. {error}</div>;

  const loadReplay = () => {
    setShowReplay(true);
    if (!replay) scoringApi.getReplay(sessionId).then(setReplay);
  };

  const loadCoverage = () => {
    if (!jdText.trim()) return;
    scoringApi.getCoverage(sessionId, jdText).then(setCoverage);
  };

  const loadPlaybooks = () => {
    if (!playbooks) scoringApi.getSessionPlaybooks(sessionId).then(setPlaybooks);
  };

  const loadModelAnswer = (index: number) => {
    scoringApi.getModelAnswer(sessionId, index).then((res) =>
      setModelAnswers((prev) => ({ ...prev, [index]: res }))
    );
  };

  return (
    <div className="scoring-page">
      <div className="scoring-hero">
        <span className="scoring-hero__label">Overall Score</span>
        <span className="scoring-hero__value">{report.overall_score.toFixed(0)}</span>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={refresh}>Recompute</button>
          <a href={scoringApi.getReportPdfUrl(sessionId)} target="_blank" rel="noreferrer">
            <button>Download PDF</button>
          </a>
        </div>
      </div>

      <RadarChart axes={report.dimensions.map((d) => ({ label: d.name, value: d.score, available: d.available }))} />

      <section>
        <h2>Dimensions</h2>
        <div className="scoring-dimensions">
          {report.dimensions.map((d) => (
            <div key={d.name} className={`scoring-dimension ${!d.available ? "scoring-dimension--unavailable" : ""}`}>
              <span>{d.name}</span>
              <span className="scoring-dimension__score">{d.available ? `${d.score.toFixed(0)}/100` : "N/A"}</span>
            </div>
          ))}
        </div>
      </section>

      {report.strengths.length > 0 && (
        <section>
          <h2>Strengths</h2>
          <ul>{report.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
        </section>
      )}

      {report.improvements.length > 0 && (
        <section>
          <h2>Areas to Improve</h2>
          <ul>{report.improvements.map((s) => <li key={s}>{s}</li>)}</ul>
        </section>
      )}

      {report.action_items.length > 0 && (
        <section>
          <h2>Next Steps</h2>
          {report.action_items.map((item, i) => (
            <div key={i} className="scoring-action-item">
              <span className={`scoring-action-item__priority scoring-action-item__priority--${item.priority}`}>
                {item.priority}
              </span>
              <div>
                <div>{item.description}</div>
                <div style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>{item.suggested_practice}</div>
              </div>
            </div>
          ))}
        </section>
      )}

      <section>
        <h2>Per-Question Breakdown</h2>
        {report.per_question_breakdown.map((qb, i) => (
          <div key={i} style={{ marginBottom: "1.5rem" }}>
            <p><strong>Q{i + 1}.</strong> {qb.question} — <span style={{ color: "var(--color-accent-primary)" }}>{qb.score.toFixed(0)}/100</span></p>
            {qb.annotated_answer && <SentenceAnnotatedAnswer annotated={qb.annotated_answer} />}
            {modelAnswers[i] ? (
              <AnswerDiffView modelAnswer={modelAnswers[i].model_answer} diff={modelAnswers[i].diff} />
            ) : (
              <button onClick={() => loadModelAnswer(i)}>See model answer</button>
            )}
          </div>
        ))}
      </section>

      <section>
        <h2>JD Coverage</h2>
        <textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="Paste the job description to check coverage..."
          rows={4}
          style={{ width: "100%" }}
        />
        <button onClick={loadCoverage}>Check coverage</button>
        {coverage && <CoverageMatrixView matrix={coverage} />}
      </section>

      <section>
        <h2>Suggested Playbooks</h2>
        <button onClick={loadPlaybooks}>Show playbooks</button>
        {playbooks?.map((p) => <PlaybookCard key={p.key} playbook={p} />)}
      </section>

      <section>
        <h2>Replay</h2>
        <button onClick={loadReplay}>{showReplay ? "Hide" : "Show"} replay</button>
        {showReplay && replay && <SessionReplay replay={replay} />}
      </section>

      <section>
        <h2>Debrief</h2>
        <button onClick={() => setShowDebrief((s) => !s)}>{showDebrief ? "Hide" : "Start"} debrief chat</button>
        {showDebrief && <DebriefChat sessionId={sessionId} />}
      </section>
    </div>
  );
}
