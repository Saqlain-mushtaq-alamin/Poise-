import type { ModelPlan } from "../../lib/types";

interface ModelConfigCardProps {
  modelPlan: ModelPlan | null;
}

export function ModelConfigCard({ modelPlan }: ModelConfigCardProps) {
  if (!modelPlan) return null;

  const rows: { role: string; model: string | null }[] = [
    { role: "Reasoning (LLM)", model: modelPlan.llm },
    { role: "Vision (VLM)", model: modelPlan.vlm },
    { role: "Speech-to-text", model: modelPlan.stt },
    { role: "Text-to-speech", model: modelPlan.tts },
    { role: "Embeddings", model: modelPlan.embedding },
  ];

  return (
    <div className="settings-card">
      <h3>Model configuration</h3>
      <table className="settings-table">
        <tbody>
          {rows.map((row) => (
            <tr key={row.role}>
              <td>{row.role}</td>
              <td className="settings-table__model">{row.model ?? "\u2014 not available at this tier"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
