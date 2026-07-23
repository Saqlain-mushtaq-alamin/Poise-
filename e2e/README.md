# E2E tests

These Playwright tests run against the Vite dev server directly (fast, no
native build required) and cover the Phase 1 acceptance criteria: app
launches, sidebar navigation works, and the theme toggle applies instantly.

```bash
cd e2e
npm install
npx playwright install --with-deps chromium
npm test
```

Playwright's config starts two servers: the Vite dev server and the real
FastAPI backend (`backend/.venv/bin/python -m app.main` on port 8000), so
Settings-page tests exercise real hardware detection rather than mocks.
Make sure `backend/.venv` exists first (`cd backend && python -m venv .venv
&& pip install -r requirements.txt`).

`voice-settings.spec.ts` additionally relies on Chromium's
`--use-fake-ui-for-media-stream` / `--use-fake-device-for-media-stream`
launch flags (already set in `playwright.config.ts`) so mic capture works
headlessly, without a real audio device or a permission-prompt click. None
of the Playwright specs in this repo have actually been run in the
environment this scaffold was built in — the browser binaries
`playwright install` downloads aren't fetchable there. Run them yourself
as the first real check of the full stack.

## Driving the real Tauri window (optional, closer to production)

To test against the compiled desktop window instead of a browser tab, use
[`tauri-driver`](https://v2.tauri.app/develop/tests/webdriver/) with a
WebDriver client (e.g. `selenium-webdriver` or Playwright's WebDriver
support is limited — `tauri-driver` speaks the W3C WebDriver protocol, so a
`webdriverio`-based suite is the common choice for this variant). That
requires a built `poise.exe`/`poise` binary and is intentionally kept out of
CI's default fast path; wire it in as a separate `e2e-native` job once a
release build is available.
