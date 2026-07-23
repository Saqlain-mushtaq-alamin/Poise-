import { defineConfig } from "@playwright/test";

// Runs against the Vite dev server directly, since driving the actual Tauri
// webview requires `tauri-driver` + WebDriver, which needs the native
// binary built (see e2e/README.md for the full desktop-driver variant).
// This config still exercises real app code — routing, theme persistence,
// sidecar status — against the same React build Tauri loads.
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 1,
  webServer: [
    {
      command: "npm run dev --prefix ../frontend",
      url: "http://localhost:1420",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command:
        "bash -c 'cd ../backend && POISE_PORT=8000 POISE_DATA_DIR=/tmp/poise-e2e ./.venv/bin/python -m app.main'",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
  use: {
    baseURL: "http://localhost:1420",
    trace: "retain-on-failure",
    // Auto-grants mic permission and feeds a synthetic tone instead of a
    // real microphone — needed for e2e/tests/voice-settings.spec.ts to run
    // in CI without a physical audio device or a permission-prompt click.
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
      ],
    },
  },
});
