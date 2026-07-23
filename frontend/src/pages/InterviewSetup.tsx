import { useEffect, useState } from "react";

import { InterviewRoom } from "../components/interview/InterviewRoom";
import { useInterviewSession } from "../hooks/useInterviewSession";
import type { PoiseAPI } from "../lib/api";
import type { CompanyFormat, InterviewConfig, Persona } from "../lib/types";

interface InterviewSetupProps {
  api: PoiseAPI | null;
}

const DEFAULT_CONFIG: Partial<InterviewConfig> = {
  duration_minutes: 30,
  include_behavioral: true,
  include_technical: true,
  include_coding: false,
  include_system_design: false,
  difficulty: "medium",
};

export function InterviewSetup({ api }: InterviewSetupProps) {
  const session = useInterviewSession(api);

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [companyFormats, setCompanyFormats] = useState<CompanyFormat[]>([]);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [personaId, setPersonaId] = useState("professional");
  const [companyFormat, setCompanyFormat] = useState<string>("");
  const [config, setConfig] = useState<Partial<InterviewConfig>>(DEFAULT_CONFIG);
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api?.listPersonas().then(setPersonas).catch(() => setPersonas([]));
    api?.listCompanyFormats().then(setCompanyFormats).catch(() => setCompanyFormats([]));
  }, [api]);

  async function handleStart() {
    if (!api) {
      setLocalError("Sidecar not connected yet");
      return;
    }
    if (!resumeFile) {
      setLocalError("Please upload a resume (.pdf or .docx)");
      return;
    }
    if (!jdText.trim()) {
      setLocalError("Please paste the job description");
      return;
    }

    setSubmitting(true);
    setLocalError(null);
    try {
      const { resume_id } = await api.parseResume(resumeFile);
      const { jd_id } = await api.parseJD(jdText);
      await session.createAndStart(
        resume_id,
        jd_id,
        { ...config, company_format: companyFormat || null },
        personaId
      );
    } catch (err) {
      setLocalError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  if (session.sessionId) {
    return (
      <div className="page">
        <h1>Interview in progress</h1>
        <InterviewRoom
          currentMessage={session.currentMessage}
          lastFeedback={session.lastFeedback}
          isComplete={session.isComplete}
          busy={session.busy}
          machineState={session.machineState}
          onSubmitWarmUp={session.respondToWarmUp}
          onSubmitAnswer={session.submitAnswer}
          onEnd={session.endSession}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Interview Mode</h1>

      {(localError || session.error) && (
        <p className="settings-card__warning">{localError || session.error}</p>
      )}

      <div className="settings-card">
        <h3>1. Resume &amp; job description</h3>
        <div className="audio-settings__row">
          <label htmlFor="resume-upload">Resume (.pdf or .docx)</label>
          <input
            id="resume-upload"
            type="file"
            accept=".pdf,.docx,.doc"
            onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="audio-settings__row">
          <label htmlFor="jd-text">Job description</label>
          <textarea
            id="jd-text"
            rows={6}
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the job description here..."
          />
        </div>
      </div>

      <div className="settings-card">
        <h3>2. Interviewer &amp; format</h3>
        <div className="audio-settings__row">
          <label htmlFor="persona-select">Interviewer persona</label>
          <select id="persona-select" value={personaId} onChange={(e) => setPersonaId(e.target.value)}>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.style}
              </option>
            ))}
          </select>
        </div>
        <div className="audio-settings__row">
          <label htmlFor="company-format-select">Company format (optional)</label>
          <select
            id="company-format-select"
            value={companyFormat}
            onChange={(e) => setCompanyFormat(e.target.value)}
          >
            <option value="">General structured format</option>
            {companyFormats.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="settings-card">
        <h3>3. Configuration</h3>
        <div className="audio-settings__row">
          <label htmlFor="duration">Duration (minutes)</label>
          <input
            id="duration"
            type="number"
            min={10}
            max={90}
            value={config.duration_minutes}
            onChange={(e) =>
              setConfig((c) => ({ ...c, duration_minutes: Number(e.target.value) }))
            }
          />
        </div>
        <div className="audio-settings__row">
          <span>Sections</span>
          <label>
            <input
              type="checkbox"
              checked={config.include_behavioral}
              onChange={(e) => setConfig((c) => ({ ...c, include_behavioral: e.target.checked }))}
            />{" "}
            Behavioral
          </label>
          <label>
            <input
              type="checkbox"
              checked={config.include_technical}
              onChange={(e) => setConfig((c) => ({ ...c, include_technical: e.target.checked }))}
            />{" "}
            Technical
          </label>
          <label>
            <input
              type="checkbox"
              checked={config.include_coding}
              onChange={(e) => setConfig((c) => ({ ...c, include_coding: e.target.checked }))}
            />{" "}
            Coding
          </label>
        </div>
      </div>

      <button type="button" onClick={handleStart} disabled={submitting || session.busy}>
        {submitting || session.busy ? "Setting up\u2026" : "Start Interview"}
      </button>
    </div>
  );
}
