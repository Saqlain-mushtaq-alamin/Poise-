/**
 * Thin wrapper over Tauri's `invoke`/`listen`. Tauri IPC is reserved for
 * window/process management (sidecar lifecycle, file dialogs, keychain) —
 * everything else (session data, scoring, etc.) goes over HTTP to the
 * FastAPI sidecar via lib/api.ts.
 *
 * Falls back to a mock implementation when `window.__TAURI__` is absent so
 * the app still renders in a plain browser during frontend-only development
 * (Vitest, Storybook-style iteration, or a phase developer working purely
 * against contracts/mocks).
 */
import type { SidecarStatus } from "./types";

const isTauri =
  typeof window !== "undefined" &&
  ("__TAURI__" in window || "__TAURI_INTERNALS__" in window);

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauri) {
    throw new Error(`Tauri IPC unavailable (not running inside Tauri): ${cmd}`);
  }
  const { invoke: tauriInvoke } = await import("@tauri-apps/api/core");
  return tauriInvoke<T>(cmd, args);
}

/** Ask the Rust side for the current sidecar status. Command implemented in
 * src-tauri/src/commands.rs as `get_sidecar_status`. */
export async function getSidecarStatus(): Promise<SidecarStatus> {
  if (!isTauri) {
    // Browser dev fallback: assume a locally-run `python -m app.main`
    // sidecar is reachable on the default dev port.
    return { port: 8000, status: "healthy", uptime_seconds: 0, restart_count: 0 };
  }
  return invoke<SidecarStatus>("get_sidecar_status");
}

/** Subscribe to sidecar status change events pushed from Rust. Returns an
 * unsubscribe function. */
export async function onSidecarStatusChange(
  callback: (status: SidecarStatus) => void
): Promise<() => void> {
  if (!isTauri) {
    return () => {};
  }
  const { listen } = await import("@tauri-apps/api/event");
  const unlisten = await listen<SidecarStatus>("sidecar-status", (event) => {
    callback(event.payload);
  });
  return unlisten;
}

export { isTauri };

// ---- Phase 2: BYOK key management (OS keychain, via src-tauri/src/keychain.rs) ----

/** Stores a provider's API key in the OS keychain and immediately pushes it
 * to the running sidecar. Throws if `provider` isn't recognized. */
export async function storeApiKey(
  provider: string,
  key: string,
  baseUrl?: string
): Promise<void> {
  if (!isTauri) {
    throw new Error("Keychain storage is unavailable outside the Tauri app");
  }
  await invoke<void>("store_api_key", { provider, key, baseUrl });
}

/** Removes a provider's key from the OS keychain (and best-effort clears
 * it from the sidecar's in-memory store too). */
export async function deleteApiKey(provider: string): Promise<void> {
  if (!isTauri) {
    throw new Error("Keychain storage is unavailable outside the Tauri app");
  }
  await invoke<void>("delete_api_key", { provider });
}

/** Which providers currently have a key stored — never the key values
 * themselves. Safe to call to render "configured" badges in Settings. */
export async function listConfiguredProviders(): Promise<string[]> {
  if (!isTauri) {
    return [];
  }
  return invoke<string[]>("list_configured_providers");
}
