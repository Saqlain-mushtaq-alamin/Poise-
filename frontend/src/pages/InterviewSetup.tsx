/**
 * InterviewSetup — Phase 4 (+ video-call upgrade).
 *
 * Step 1: User uploads resume + JD, picks persona, format, model, config.
 * Step 2: After clicking "Start Interview", the full-screen
 *         VideoCallInterviewRoom replaces this form — the AI conducts the
 *         interview via voice, detects pauses via VAD, and the user can
 *         also code in a sandboxed editor when the question requires it.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { VideoCallInterviewRoom } from "../components/interview/VideoCallInterviewRoom";
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
  {
    id: "professional",
    name: "Professional Recruiter",
    style: "Formal and structured",
    voice: "en-US-AvaNeural",
    system_prompt: "",
  },
  {
    id: "friendly",
    name: "Friendly Peer",
    style: "Casual and encouraging",
    voice: "en-US-JennyNeural",
    system_prompt: "",
  },
  {
    id: "tough",
    name: "Strict Technical Lead",
    style: "Direct and challenging",
    voice: "en-US-GuyNeural",
    system_prompt: "",
  },
];

const DEFAULT_COMPANY_FORMATS: CompanyFormat[] = [
  {
    id: "faang",
    name: "FAANG / Big Tech",
    structure: ["Behavioral", "Technical"],
    framework: "STAR",
    scoring_note: "Rigorous evaluation",
    principles: ["Leadership"],
  },
  {
    id: "startup",
    name: "Fast-Paced Startup",
    structure: ["Practical", "Culture"],
    framework: "Agile",
    scoring_note: "Focus on execution",
    principles: ["Ownership"],
  },
];

export function InterviewSetup({ api }: InterviewSetupProps) {
  const session = useInterviewSession(api);
  const navigate = useNavigate();

  const [personas, setPersonas] = useState<Persona[]>(DEFAULT_PERSONAS);
  const [companyFormats, setCompanyFormats] = useState<CompanyFormat[]>(DEFAULT_COMPANY_FORMATS);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [personaId, setPersonaId] = useState("professional");
  const [companyFormat, setCompanyFormat] = useState<string>("");
  const [config, setConfig] = useState<Partial<InterviewConfig>>(DEFAULT_CONFIG);
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dragOver, setDragOver] = useState(false);

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

      api
        .getModelConfig<{ selected_model: string; available_models: string[] }>()
        .then((res) => {
          if (res.available_models?.length) setAvailableModels(res.available_models);
          if (res.selected_model) setSelectedModel(res.selected_model);
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

  // ── Active interview — show full-screen video-call room ──
  if (session.sessionId) {
    const selectedPersona = personas.find((p) => p.id === personaId) ?? DEFAULT_PERSONAS[0];
    const backendBaseUrl = api?.baseUrlValue ?? api?.baseUrl ?? "http://127.0.0.1:8000";
    const hasCoding = !!config.include_coding;

    return (
      <VideoCallInterviewRoom
        currentMessage={session.currentMessage}
        lastFeedback={session.lastFeedback}
        isComplete={session.isComplete}
        busy={session.busy}
        machineState={session.machineState}
        onSubmitWarmUp={session.respondToWarmUp}
        onSubmitAnswer={session.submitAnswer}
        onEnd={() => {
          const id = session.sessionId;
          session.endSession();
          if (id) navigate(`/report/${id}`);
        }}
        onBack={() => {
          session.endSession();
          session.resetSession();
        }}
        backendBaseUrl={backendBaseUrl}
        personaName={selectedPersona.name}
        personaVoice={selectedPersona.voice ?? "en-US-AvaNeural"}
        enableCoding={hasCoding}
        sessionId={session.sessionId}
      />
    );
  }

  // ── Setup form ──
  const selectedPersona = personas.find((p) => p.id === personaId) ?? DEFAULT_PERSONAS[0];

  return (
    <div className="is-page">
      {/* Header */}
      <div className="is-header">
        <div className="is-header__icon">🎙️</div>
        <div>
          <h1 className="is-header__title">Mock Interview</h1>
          <p className="is-header__sub">
            Upload your resume and job description to start a realistic AI-conducted video
            interview with voice, VAD silence detection, and optional coding rounds.
          </p>
        </div>
      </div>

      {/* Error banner */}
      {(!api || localError || session.error) && (
        <div className="is-banner is-banner--warn">
          {!api
            ? "⚠️ Sidecar not connected — start the backend or wait for it to initialize."
            : localError || session.error}
        </div>
      )}

      <div className="is-grid">
        {/* ── Card 1: Resume + JD ── */}
        <div className="is-card">
          <div className="is-card__header">
            <div className="is-card__step">01</div>
            <h2 className="is-card__title">Resume & Job Description</h2>
          </div>

          {/* Resume drop zone */}
          <div
            className={`is-dropzone${dragOver ? " is-dropzone--active" : ""}${resumeFile ? " is-dropzone--filled" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const file = e.dataTransfer.files?.[0];
              if (file) setResumeFile(file);
            }}
            onClick={() => document.getElementById("resume-upload")?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload resume"
            onKeyDown={(e) => e.key === "Enter" && document.getElementById("resume-upload")?.click()}
          >
            <input
              id="resume-upload"
              type="file"
              accept=".pdf,.docx,.doc"
              style={{ display: "none" }}
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
            />
            {resumeFile ? (
              <>
                <span className="is-dropzone__icon">📄</span>
                <span className="is-dropzone__filename">{resumeFile.name}</span>
                <span className="is-dropzone__hint">Click to change</span>
              </>
            ) : (
              <>
                <span className="is-dropzone__icon">📂</span>
                <span className="is-dropzone__label">Drop your resume here</span>
                <span className="is-dropzone__hint">.pdf, .docx, .doc · click or drag</span>
              </>
            )}
          </div>

          {/* Job description */}
          <div className="is-field">
            <label htmlFor="jd-text" className="is-label">Job Description</label>
            <textarea
              id="jd-text"
              className="is-textarea"
              rows={6}
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste the full job description here…"
            />
          </div>
        </div>

        {/* ── Card 2: Interviewer & format ── */}
        <div className="is-card">
          <div className="is-card__header">
            <div className="is-card__step">02</div>
            <h2 className="is-card__title">Interviewer & Format</h2>
          </div>

          {/* Persona cards */}
          <div className="is-persona-grid">
            {personas.map((p) => (
              <button
                key={p.id}
                id={`persona-${p.id}`}
                className={`is-persona-card${personaId === p.id ? " is-persona-card--selected" : ""}`}
                onClick={() => setPersonaId(p.id)}
                type="button"
                title={p.style}
              >
                <span className="is-persona-card__avatar">
                  {p.id === "professional" ? "👔" : p.id === "friendly" ? "😊" : "🧑‍💻"}
                </span>
                <span className="is-persona-card__name">{p.name}</span>
                <span className="is-persona-card__style">{p.style}</span>
              </button>
            ))}
          </div>

          {/* Selected persona voice preview */}
          <div className="is-persona-voice-row">
            <span className="is-label">AI Voice</span>
            <span className="is-persona-voice-badge">
              🎙 {selectedPersona.voice ?? "en-US-AvaNeural"}
            </span>
          </div>

          {/* Company format */}
          <div className="is-field">
            <label htmlFor="company-format-select" className="is-label">
              Company Format <span className="is-label__opt">(optional)</span>
            </label>
            <select
              id="company-format-select"
              className="is-select"
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

          {/* AI model */}
          <div className="is-field">
            <label htmlFor="model-select" className="is-label">
              AI Model
              {modelSaving && <span className="is-label__saving"> (saving…)</span>}
            </label>
            {availableModels.length > 0 ? (
              <select
                id="model-select"
                className="is-select"
                value={selectedModel}
                onChange={(e) => handleModelChange(e.target.value)}
                disabled={modelSaving}
              >
                {availableModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <span className="is-label__muted">
                {api ? "Loading models…" : "Connect sidecar to see models"}
              </span>
            )}
          </div>
        </div>

        {/* ── Card 3: Config ── */}
        <div className="is-card">
          <div className="is-card__header">
            <div className="is-card__step">03</div>
            <h2 className="is-card__title">Session Configuration</h2>
          </div>

          <div className="is-field">
            <label htmlFor="duration" className="is-label">Duration (minutes)</label>
            <div className="is-slider-row">
              <input
                id="duration"
                type="range"
                min={10}
                max={90}
                step={5}
                value={config.duration_minutes}
                onChange={(e) =>
                  setConfig((c) => ({ ...c, duration_minutes: Number(e.target.value) }))
                }
                className="is-slider"
              />
              <span className="is-slider__val">{config.duration_minutes} min</span>
            </div>
          </div>

          <div className="is-field">
            <span className="is-label">Interview Sections</span>
            <div className="is-toggle-row">
              {(
                [
                  { key: "include_behavioral", label: "Behavioral", icon: "🗣️" },
                  { key: "include_technical", label: "Technical", icon: "⚙️" },
                  { key: "include_coding", label: "Coding", icon: "💻" },
                  { key: "include_system_design", label: "System Design", icon: "🏗️" },
                ] as const
              ).map(({ key, label, icon }) => (
                <button
                  key={key}
                  id={`toggle-${key}`}
                  type="button"
                  className={`is-toggle${config[key] ? " is-toggle--on" : ""}`}
                  onClick={() => setConfig((c) => ({ ...c, [key]: !c[key] }))}
                  aria-pressed={!!config[key]}
                >
                  <span>{icon}</span>
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="is-field">
            <span className="is-label">Difficulty</span>
            <div className="is-difficulty-row">
              {(["easy", "medium", "hard"] as const).map((d) => (
                <button
                  key={d}
                  id={`difficulty-${d}`}
                  type="button"
                  className={`is-difficulty-btn${config.difficulty === d ? " is-difficulty-btn--active" : ""}`}
                  onClick={() => setConfig((c) => ({ ...c, difficulty: d }))}
                  aria-pressed={config.difficulty === d}
                >
                  {d === "easy" ? "🟢" : d === "medium" ? "🟡" : "🔴"} {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── CTA ── */}
      <div className="is-cta">
        <button
          id="start-interview-btn"
          type="button"
          className="is-start-btn"
          onClick={handleStart}
          disabled={!api || submitting || session.busy}
        >
          {submitting || session.busy ? (
            <>
              <span className="is-start-btn__spinner" />
              Setting up interview…
            </>
          ) : (
            <>
              <span>🎙️</span>
              Start Mock Interview
            </>
          )}
        </button>
        <p className="is-cta__hint">
          The AI will speak your first question aloud. Speak your answer — a{" "}
          <strong>2.5 second pause</strong> will auto-submit it. You can also type if preferred.
        </p>
      </div>
    </div>
  );
}
