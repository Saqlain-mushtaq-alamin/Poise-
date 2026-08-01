// frontend/src/lib/sentry.ts
// Phase 9.6 — Sentry integration, disabled by default (Settings toggle).
//
// npm install @sentry/react @sentry/tracing
//
// MERGE NOTE: the DSN should come from a build-time env var, never hardcoded.
// Wire `getSentryOptIn` / `setSentryOptIn` to your real settings store
// (same one used for theme, tier, etc. from Phase 1).

import * as Sentry from "@sentry/react";
import type { PoiseError } from "./errors";

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
let initialized = false;

const SETTINGS_KEY = "sentryOptIn";

export function getSentryOptIn(): boolean {
  // TODO(merge): replace with real settings read.
  return localStorage.getItem(SETTINGS_KEY) === "true";
}

export function setSentryOptIn(enabled: boolean): void {
  // TODO(merge): replace with real settings write (and re-init/teardown below).
  localStorage.setItem(SETTINGS_KEY, String(enabled));
  if (enabled) {
    initSentry();
  } else {
    teardownSentry();
  }
}

export function initSentry(): void {
  if (initialized || !SENTRY_DSN || !getSentryOptIn()) return;

  Sentry.init({
    dsn: SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
    // Never send PII: no default IP capture, no request bodies/headers,
    // strip anything under `user` before sending.
    sendDefaultPii: false,
    beforeSend(event) {
      delete event.user;
      if (event.request) {
        delete event.request.cookies;
        delete event.request.headers;
      }
      return event;
    },
  });
  initialized = true;
}

export function teardownSentry(): void {
  if (!initialized) return;
  Sentry.close(2000);
  initialized = false;
}

export function captureException(error: PoiseError, extra?: Record<string, unknown>): void {
  if (!initialized) return; // opt-in only — never send anything otherwise
  Sentry.captureException(error, {
    tags: { category: error.category },
    extra,
  });
}

/** Manual trigger for the Phase 9 acceptance test: "Sentry captures a test crash event". */
export function sendTestCrash(): void {
  if (!initialized) {
    console.warn("Sentry is not enabled — turn it on in Settings > Privacy first.");
    return;
  }
  Sentry.captureMessage("Poise test crash event", "info");
}
