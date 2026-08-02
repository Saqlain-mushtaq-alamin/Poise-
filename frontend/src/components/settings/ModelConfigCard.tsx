import { useEffect, useState } from "react";
import type { PoiseAPI } from "../../lib/api";
import type { ModelPlan } from "../../lib/types";

interface ModelConfigCardProps {
  modelPlan: ModelPlan | null;
  api?: PoiseAPI | null;
  ollamaModels?: string[];
  onModelChange?: () => void;
}

export function ModelConfigCard({ modelPlan, api, ollamaModels = [], onModelChange }: ModelConfigCardProps) {
  const [selectedModel, setSelectedModel] = useState<string>(modelPlan?.llm ?? "");
  const [availableModels, setAvailableModels] = useState<string[]>(ollamaModels);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (modelPlan?.llm) {
      setSelectedModel(modelPlan.llm);
    }
  }, [modelPlan?.llm]);

  useEffect(() => {
    if (api) {
      api
        .getModelConfig<{ selected_model: string; available_models: string[] }>()
        .then((res) => {
          if (res.selected_model) setSelectedModel(res.selected_model);
          if (res.available_models && res.available_models.length) {
            setAvailableModels(res.available_models);
          }
        })
        .catch(() => {});
    }
  }, [api]);

  const allModels = Array.from(new Set([...ollamaModels, ...availableModels, selectedModel])).filter(Boolean);

  async function handleSelectModel(modelName: string) {
    setSelectedModel(modelName);
    if (!api) return;
    setSaving(true);
    try {
      await api.setModelConfig(modelName);
      onModelChange?.();
    } catch {
      // Best effort
    } finally {
      setSaving(false);
    }
  }

  if (!modelPlan) return null;

  return (
    <div className="settings-card">
      <h3>Model Configuration &amp; Selection</h3>
      <p className="page__placeholder-note" style={{ marginBottom: "1rem" }}>
        Choose which model to run for interview practice &amp; IELTS sessions. Detected local Ollama models are listed below.
      </p>
      <table className="settings-table">
        <tbody>
          <tr>
            <td>
              <strong>Reasoning (LLM)</strong>
            </td>
            <td className="settings-table__model">
              {allModels.length > 0 ? (
                <select
                  value={selectedModel}
                  onChange={(e) => handleSelectModel(e.target.value)}
                  disabled={saving}
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border, #333)",
                    background: "var(--bg-secondary, #1e1e1e)",
                    color: "inherit",
                    fontSize: "0.9rem",
                    width: "100%",
                    maxWidth: "320px",
                  }}
                >
                  {allModels.map((m) => (
                    <option key={m} value={m}>
                      {m} {m === modelPlan.llm ? " (Active)" : ""}
                    </option>
                  ))}
                </select>
              ) : (
                <span>{selectedModel || modelPlan.llm}</span>
              )}
            </td>
          </tr>
          <tr>
            <td>Vision (VLM)</td>
            <td className="settings-table__model">{modelPlan.vlm ?? "\u2014 not available at this tier"}</td>
          </tr>
          <tr>
            <td>Speech-to-text</td>
            <td className="settings-table__model">{modelPlan.stt}</td>
          </tr>
          <tr>
            <td>Text-to-speech</td>
            <td className="settings-table__model">{modelPlan.tts}</td>
          </tr>
          <tr>
            <td>Embeddings</td>
            <td className="settings-table__model">{modelPlan.embedding}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
