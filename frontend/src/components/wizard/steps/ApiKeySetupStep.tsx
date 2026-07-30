// frontend/src/components/wizard/steps/ApiKeySetupStep.tsx
//
// Merge notes: keys are written to the OS keychain via the Phase 2
// provider layer, never to a plaintext config file (see Phase 9.9 security
// hardening). `saveApiKey` should call your existing Tauri command, e.g.
// `invoke("save_provider_key", { provider, key })` which stores it with
// the `keyring` crate / OS credential manager.
import { useState } from "react";
import type { StepProps } from "../FirstRunWizard";
import { invokeSidecar } from "../../../lib/api";

const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "google", label: "Google (Gemini)" },
];

async function testConnection(provider: string, key: string): Promise<boolean> {
  const res = await invokeSidecar<{ valid: boolean }>("POST", "/providers/test-key", { provider, key });
  return res.valid;
}

async function saveApiKey(provider: string, key: string): Promise<void> {
  // TODO(merge): swap for the real Tauri command that writes to the OS
  // keychain, e.g. `await invoke("save_provider_key", { provider, key })`.
  await invokeSidecar("POST", "/providers/save-key", { provider, key });
}

export function ApiKeySetupStep({ state, setState, onNext, onSkip }: StepProps) {
  const [provider, setProvider] = useState(state.apiProvider ?? PROVIDERS[0].id);
  const [key, setKey] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"idle" | "valid" | "invalid">("idle");

  const handleTest = async () => {
    setTesting(true);
    setTestResult("idle");
    try {
      const valid = await testConnection(provider, key);
      setTestResult(valid ? "valid" : "invalid");
      if (valid) {
        await saveApiKey(provider, key);
        setState((s) => ({ ...s, apiProvider: provider, apiKeyValid: true }));
      }
    } catch {
      setTestResult("invalid");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="wizard-step">
      <h1>Connect your API key</h1>
      <p className="wizard-step__subtitle">
        Your key is stored in your OS keychain and never leaves your machine except to call the
        provider you choose.
      </p>

      <label className="wizard-field">
        <span>Provider</span>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>

      <label className="wizard-field">
        <span>API key</span>
        <input
          type="password"
          value={key}
          onChange={(e) => {
            setKey(e.target.value);
            setTestResult("idle");
          }}
          placeholder="sk-..."
          autoComplete="off"
        />
      </label>

      <button
        type="button"
        className="wizard-btn wizard-btn--secondary"
        onClick={handleTest}
        disabled={!key || testing}
      >
        {testing ? "Testing…" : "Test connection"}
      </button>

      {testResult === "valid" && <p className="wizard-success-text">Connection successful.</p>}
      {testResult === "invalid" && (
        <p className="wizard-error-text" role="alert">
          That key was rejected. Double-check it and try again.
        </p>
      )}

      <div className="wizard-step__actions">
        <button
          type="button"
          className="wizard-btn wizard-btn--primary"
          onClick={onNext}
          disabled={!state.apiKeyValid}
        >
          Continue
        </button>
        {onSkip && (
          <button type="button" className="wizard__link-btn" onClick={onSkip}>
            Skip for now
          </button>
        )}
      </div>
    </div>
  );
}
