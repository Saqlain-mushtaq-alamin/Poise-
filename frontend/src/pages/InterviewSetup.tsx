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

const DEFAULT_PERSONAS: Persona[] = [
  { id: "professional", name: "Professional Recruiter", style: "Formal and structured", voice: "alloy", system_prompt: "" },
  { id: "friendly", name: "Friendly Peer", style: "Casual and encouraging", voice: "echo", system_prompt: "" },
  { id: "tough", name: "Strict Technical Lead", style: "Direct and challenging", voice: "onyx", system_prompt: "" },
];

const DEFAULT_COMPANY_FORMATS: CompanyFormat[] = [
  { id: "faang", name: "FAANG / Big Tech", structure: ["Behavioral", "Technical"], framework: "STAR", scoring_note: "Rigorous evaluation", principles: ["Leadership"] },
  { id: "startup", name: "Fast-Paced Startup", structure: ["Practical", "Culture"], framework: "Agile", scoring_note: "Focus on execution", principles: ["Ownership"] },
];

export function InterviewSetup({ api }: InterviewSetupProps) {
  const session = useInterviewSession(api);

  const [personas, setPersonas] = useState<Persona[]>(DEFAULT_PERSONAS);
  const [companyFormats, setCompanyFormats] = useState<CompanyFormat[]>(DEFAULT_COMPANY_FORMATS);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [personaId, setPersonaId] = useState("professional");
  const [companyFormat, setCompanyFormat] = useState<string>("");
  const [config, setConfig] = useState<Partial<InterviewConfig>>(DEFAULT_CONFIG);
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Ollama model selection
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelSaving, setModelSaving] = useState(false);

  useEffect(() => {
    if (api) {
      api
        .listPersonas<Persona[]>()
        .then((res) => setPersonas(res && res.length ? res : DEFAULT_PERSONAS))
        .catch(() => setPersonas(DEFAULT_PERSONAS));

      api
        .listCompanyFormats<CompanyFormat[]>()
        .then((res) => setCompanyFormats(res && res.length ? res : DEFAULT_COMPANY_FORMATS))
        .catch(() => setCompanyFormats(DEFAULT_COMPANY_FORMATS));

      // Load available Ollama models + currently selected model
      api
        .getModelConfig<{ selected_model: string; available_models: string[] }>()
        .then((res) => {
          if (res.available_models && res.available_models.length) {
            setAvailableModels(res.available_models);
          }
          if (res.selected_model) {
            setSelectedModel(res.selected_model);
          }
        })
        .catch(() => {});
    }
  }, [api]);

  async function handleModelChange(modelName: string) {
    setSelectedModel(modelName);
    if (!api) return;
    setModelSaving(true);
    try {
      await api.setModelConfig(modelName);
    } catch {
      // best effort
    } finally {
      setModelSaving(false);
    }
  }

  async function handleStart() {
    if (!api) {
      setLocalError("Sidecar not connected yet — please wait for the backend to start.");
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
      const { resume_id } = await api.parseResume<{ resume_id: string }>(resumeFile);
      const { jd_id } = await api.parseJD<{ jd_id: string }>(jdText);
      await session.createAndStart(
        resume_id,
        jd_id,
        { ...config, company_format: companyFormat || null },
        personaId
      );
    } catch (err) {
      const msg = (err as Error).message ?? String(err);
      // Make common provider errors actionable
      if (
        msg.includes("no API key") ||
        msg.includes("API key") ||
        msg.includes("Cloud Assist") ||
        msg.includes("provider") ||
        msg.includes("No model configured")
      ) {
        setLocalError(
          `LLM not configured: ${msg}. Go to Settings → Hardware & model providers to add an API key or select Ollama.`
        );
      } else {
        setLocalError(msg);
      }
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

      {!api && (
        <p className="settings-card__warning">
          ⚠️ Sidecar not connected — start the backend or wait a moment for it to initialize.
        </p>
      )}

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
        <div className="audio-settings__row">
          <label htmlFor="model-select">
            AI model
            {modelSaving && <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", opacity: 0.7 }}>(saving…)</span>}
          </label>
          {availableModels.length > 0 ? (
            <select
              id="model-select"
              value={selectedModel}
              onChange={(e) => handleModelChange(e.target.value)}
              disabled={modelSaving}
            >
              {availableModels.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          ) : (
            <span style={{ opacity: 0.6 }}>
              {api ? "Loading models…" : "Connect sidecar to see models"}
            </span>
          )}
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
        <div className="audio-settings__row">
          <label htmlFor="difficulty-select">Difficulty</label>
          <select
            id="difficulty-select"
            value={config.difficulty ?? "medium"}
            onChange={(e) =>
              setConfig((c) => ({
                ...c,
                difficulty: e.target.value as "easy" | "medium" | "hard",
              }))
            }
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
      </div>

      <button type="button" onClick={handleStart} disabled={!api || submitting || session.busy}>
        {submitting || session.busy ? "Setting up…" : "Start Interview"}
      </button>
    </div>
  );
}
