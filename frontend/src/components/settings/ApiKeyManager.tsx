import { useState } from "react";

import type { ApiProvider, TestConnectionResult } from "../../lib/types";

const PROVIDERS: { id: ApiProvider; label: string; placeholder: string }[] = [
  { id: "openai", label: "OpenAI", placeholder: "sk-..." },
  { id: "anthropic", label: "Anthropic", placeholder: "sk-ant-..." },
  { id: "google", label: "Google (Gemini)", placeholder: "AI Studio API key" },
  { id: "groq", label: "Groq", placeholder: "gsk_..." },
  { id: "custom", label: "Custom (OpenAI-compatible)", placeholder: "API key (optional)" },
];

interface ApiKeyManagerProps {
  configuredProviders: string[];
  onStore: (provider: string, key: string, baseUrl?: string) => Promise<void>;
  onDelete: (provider: string) => Promise<void>;
  onTest: (provider: string, key?: string, baseUrl?: string) => Promise<TestConnectionResult>;
}

export function ApiKeyManager({
  configuredProviders,
  onStore,
  onDelete,
  onTest,
}: ApiKeyManagerProps) {
  return (
    <div className="settings-card">
      <h3>API keys (BYOK)</h3>
      <p className="page__placeholder-note">
        Keys are stored in your OS keychain, never in Poise's database, and never leave your
        machine except in requests to the provider you choose.
      </p>
      {PROVIDERS.map((provider) => (
        <ApiKeyRow
          key={provider.id}
          provider={provider.id}
          label={provider.label}
          placeholder={provider.placeholder}
          configured={configuredProviders.includes(provider.id)}
          onStore={onStore}
          onDelete={onDelete}
          onTest={onTest}
        />
      ))}
    </div>
  );
}

interface ApiKeyRowProps {
  provider: ApiProvider;
  label: string;
  placeholder: string;
  configured: boolean;
  onStore: (provider: string, key: string, baseUrl?: string) => Promise<void>;
  onDelete: (provider: string) => Promise<void>;
  onTest: (provider: string, key?: string, baseUrl?: string) => Promise<TestConnectionResult>;
}

function ApiKeyRow({
  provider,
  label,
  placeholder,
  configured,
  onStore,
  onDelete,
  onTest,
}: ApiKeyRowProps) {
  const [key, setKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);

  async function handleTest() {
    setBusy(true);
    setTestResult(null);
    try {
      const result = await onTest(provider, key || undefined, baseUrl || undefined);
      setTestResult(result);
    } catch (err) {
      setTestResult({
        provider,
        success: false,
        latency_ms: null,
        models_available: null,
        error: (err as Error).message,
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    setBusy(true);
    setTestResult(null);
    try {
      await onStore(provider, key, baseUrl || undefined);
      setKey("");
    } catch (err) {
      setTestResult({
        provider,
        success: false,
        latency_ms: null,
        models_available: null,
        error: (err as Error).message,
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    try {
      await onDelete(provider);
      setTestResult(null);
    } catch (err) {
      setTestResult({
        provider,
        success: false,
        latency_ms: null,
        models_available: null,
        error: (err as Error).message,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="api-key-row">
      <div className="api-key-row__label">
        <span>{label}</span>
        <span className={`api-key-row__badge${configured ? " api-key-row__badge--on" : ""}`}>
          {configured ? "Configured" : "Not configured"}
        </span>
      </div>

      {provider === "custom" && (
        <input
          type="text"
          placeholder="Base URL, e.g. https://my-proxy.example.com/v1"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          aria-label={`${label} base URL`}
        />
      )}

      <input
        type="password"
        placeholder={placeholder}
        value={key}
        onChange={(e) => setKey(e.target.value)}
        aria-label={`${label} API key`}
      />

      <div className="api-key-row__actions">
        <button type="button" onClick={handleTest} disabled={busy}>
          Test connection
        </button>
        <button type="button" onClick={handleSave} disabled={busy || !key}>
          Save
        </button>
        {configured && (
          <button type="button" onClick={handleDelete} disabled={busy} className="api-key-row__remove">
            Remove
          </button>
        )}
      </div>

      {testResult && (
        <p
          className={`api-key-row__result${testResult.success ? " api-key-row__result--ok" : " api-key-row__result--error"}`}
        >
          {testResult.success
            ? `Connected — ${testResult.latency_ms}ms, ${testResult.models_available} models available`
            : `Failed: ${testResult.error}`}
        </p>
      )}
    </div>
  );
}
