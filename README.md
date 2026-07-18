# Poise

Offline-first desktop coach for interview practice and IELTS speaking —
Tauri (Rust) shell + React frontend + FastAPI sidecar, zero hosted backend.

This repo currently implements **Phase 1 — Foundation Shell** and
**Phase 2 — Hardware Detection & Model Provider Layer** of the
[master development plan](planning/development-plan/00-master-plan.md).
See `planning/development-plan/01-foundation-shell.md` and
`planning/development-plan/02-hardware-providers.md` for the full specs
these phases were built against.

## What's here

```
poise/
├── src-tauri/        # Tauri v2 Rust shell: window, sidecar lifecycle, IPC, OS keychain (BYOK)
├── frontend/          # React + Vite app (the webview content)
├── backend/           # FastAPI sidecar: health, settings, hardware, provider router, setup wizard
├── contracts/         # OpenAPI specs, shared TS types, IPC event schemas, mocks
├── e2e/               # Playwright E2E tests
├── scripts/           # Sidecar packaging (PyInstaller → Tauri externalBin)
└── planning/          # Development plan docs
```

## Prerequisites

- Node.js 20+
- Python 3.10+
- Rust stable + platform build tools for Tauri v2 — follow the
  [official prerequisites guide](https://v2.tauri.app/start/prerequisites/)
  for your OS (on Windows: MSVC build tools + WebView2, already present on
  most Windows 10/11 installs)
- (Optional, for local tiers) [Ollama](https://ollama.com) running locally,
  and/or Docker

## Running in development

```bash
# 1. Backend deps (one-time)
cd backend
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head              # creates the SQLite DB
cd ..

# 2. Frontend deps (one-time)
cd frontend
npm install
cd ..

# 3. Launch the app — Tauri starts Vite AND spawns `python -m app.main`
#    as the dev sidecar automatically (see src-tauri/tauri.conf.json
#    beforeDevCommand, and src-tauri/src/sidecar.rs for the spawn logic)
cd src-tauri
cargo tauri dev
```

> Rust/Tauri were not compiled in the environment this scaffold was
> generated in (no Rust toolchain available there). The FastAPI backend and
> React frontend below **were** installed, run, and verified end-to-end —
> Rust code (including the new `src-tauri/src/keychain.rs`) follows the
> Tauri v2 / `keyring` crate API surface as documented but hasn't been
> `cargo check`ed. Run `cargo check` inside `src-tauri/` as your first step
> and treat any compiler errors it surfaces as the next task, not a sign the
> architecture is wrong.

## Verified working (in this scaffold's build environment)

- **Backend**: 80/80 pytest tests pass (9 from Phase 1, 71 new for Phase 2);
  `ruff check .` is clean. The sidecar was actually booted and its new
  endpoints hit for real: `/hardware/profile` correctly detected this
  sandbox as a GPU-less, low-RAM Linux box and `/hardware/tier` correctly
  recommended `cloud_assist` for it — real detection logic running against
  real (if unglamorous) hardware, not just mocked tests.
- **Frontend**: 29/29 Vitest tests pass across 8 files (9 from Phase 1, 20
  new for Phase 2); `tsc -b --noEmit` is clean; `eslint --max-warnings 0`
  is clean; `vite build` produces a working production bundle.
- **Not yet compiled**: the Rust/Tauri shell (`src-tauri/`), including the
  new OS-keychain BYOK module — no Rust toolchain was available in the
  scaffold environment. See note above.
- **Not exercised end-to-end**: real cloud provider calls (OpenAI/Anthropic/
  etc.) and real Ollama model pulls — the sandbox has no route to those
  hosts and no Ollama installed. All provider-router and setup-wizard logic
  is covered by tests with `litellm`/`httpx` calls mocked instead.

## Testing

```bash
# Backend
cd backend && pytest -q && ruff check .

# Frontend
cd frontend && npm run typecheck && npm run lint && npm test

# E2E (against the Vite dev server + a real FastAPI backend; see
# e2e/README.md for driving the actual compiled Tauri window instead)
cd e2e && npm install && npx playwright install --with-deps chromium && npm test
```

## Building for distribution

```bash
bash scripts/build-sidecar.sh   # PyInstaller → src-tauri/binaries/poise-backend-<target-triple>
cd src-tauri
cargo tauri build
```

## Phase 2 architecture notes

- **Tier override, not a new table.** The chosen hardware tier persists
  through Phase 1's generic `AppSettings` key/value table (key
  `hardware_tier_override`) rather than a bespoke column — no new Alembic
  migration was needed.
- **BYOK keys are memory-only in the backend.** `ModelProviderRouter` holds
  keys in a plain dict for the sidecar process's lifetime. The OS keychain
  (via `src-tauri/src/keychain.rs` and the `keyring` crate) is the actual
  durable store; on a healthy sidecar report, Rust reads every known
  provider's key back out of the keychain and `PUT`s it to
  `/provider/keys/{provider}` so a restarted app doesn't need the user to
  re-enter anything. Nothing provider-related is ever written to SQLite or
  logged.
- **`ModelRole.PRONUNCIATION` is hardcoded to `wav2vec2`** regardless of
  tier, per the spec — pronunciation scoring never leaves the machine.
- **Cost cap is a soft warning, not a hard stop.** `/provider/cost` reports
  `cap_warning: true` once either the token or dollar threshold is crossed;
  enforcing an actual stop is left to whichever phase makes the cloud call
  in context (Phase 4/6/7), since only they know if it's safe to
  interrupt mid-session.

## Acceptance criteria status (Phase 2 spec, §"Acceptance Criteria")

| Criterion | Status |
|---|---|
| Hardware detection correctly identifies GPU/RAM/CPU on Windows+NVIDIA | Code complete, verified on Linux (no NVIDIA GPU in scaffold env); NVIDIA CSV-parsing path covered by unit tests with mocked `nvidia-smi` output |
| Tier recommendation matches expected result for 3+ device profiles | ✅ Verified — 13 mocked profiles, all pass |
| LiteLLM routes to Ollama on Local Full with Ollama running | Code complete (`ollama/<model>` routing); unverified live (no Ollama in scaffold env) — covered by mocked unit test |
| LiteLLM routes to OpenAI on Cloud Assist with a valid key | Code complete; unverified live (no network route to api.openai.com) — covered by mocked unit test |
| API key stored in OS keychain, survives restart, never logged | Code complete (`keychain.rs` + rehydration on sidecar-healthy); unverified (no Rust toolchain) |
| Test-connection endpoint validates key and returns latency | ✅ Verified via mocked HTTP round-trip; real-provider call unverified (no network route) |
| Token counter accurately tracks usage across a multi-turn conversation | ✅ Verified — accumulates correctly across multiple calls/models |
| Cost warning fires when approaching the configurable cap | ✅ Verified — both token-threshold and dollar-threshold triggers tested |
| Graceful error when Ollama not running / cloud key invalid | ✅ Verified — `ProviderError` raised with a clear message in both cases |
| Settings UI shows tier, allows override, manages keys with masked display | ✅ Verified — `type="password"` inputs, all UI interactions covered by Vitest |

## Handoff notes for the next phases

- **Phase 4 (Interview Engine):** `from app.services.provider import get_router, ModelRole` then
  `await get_router().chat(messages, model_role=ModelRole.REASONING)`. You never need to know
  whether that's Ollama or a cloud model.
- **Phase 6 (Coding Sandbox):** use `ModelRole.VISION` for screen/whiteboard reading — note it
  raises `ProviderError` on Local Lite, which has no VLM in its model plan.
- **Phase 8 (Scoring & Progress):** call `get_router().get_cost_estimate()` for the session cost
  line in the report; `contracts/mocks/mock-scores.json` has a fixture to build against meanwhile.
- **Phase 3 (Voice Pipeline):** `ModelRole.PRONUNCIATION` always resolves to `"wav2vec2"` regardless
  of tier — you don't need to route around cloud fallbacks for it. Add audio components under
  `frontend/src/components/`; `contracts/api/voice.yaml` is stubbed and waiting for you.
- **Phase 5 (Webcam Analysis):** `Shell.tsx` has a reserved `#webcam-overlay-slot` div for your
  always-on overlay.
