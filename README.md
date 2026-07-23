# Poise

Offline-first desktop coach for interview practice and IELTS speaking —
Tauri (Rust) shell + React frontend + FastAPI sidecar, zero hosted backend.

This repo currently implements **Phase 1 — Foundation Shell**,
**Phase 2 — Hardware Detection & Model Provider Layer**,
**Phase 3 — Voice Pipeline (STT + TTS + VAD)**,
**Phase 4 — Interview Engine**, and
**Phase 5 — Webcam Confidence Analysis Pipeline** of the
[master development plan](planning/development-plan/00-master-plan.md).
See `planning/development-plan/01-foundation-shell.md`,
`02-hardware-providers.md`, `03-voice-pipeline.md`, `04-interview-engine.md`,
and `05-webcam-analysis.md` for the full specs these phases were built
against.

## What's here

```
poise/
├── src-tauri/        # Tauri v2 Rust shell: window, sidecar lifecycle, IPC, OS keychain (BYOK)
├── frontend/          # React + Vite app; public/worklets/ has the real AudioWorklet processor;
│                       #   src/machines/ has the XState interview session machine;
│                       #   src/services/vision/ has the webcam confidence analyzers
├── backend/           # FastAPI sidecar: health, settings, hardware, provider router,
│                       #   setup wizard, VAD/STT/TTS voice pipeline, interview engine,
│                       #   webcam confidence aggregation
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

- **Backend**: 289/289 pytest tests pass (9 Phase 1, 71 Phase 2, 54 Phase 3,
  123 Phase 4, 32 Phase 5); `ruff check .` is clean. The sidecar was
  actually booted and hit for real: `/hardware/profile` correctly
  detected this sandbox as a GPU-less, low-RAM Linux box; `POST /voice/tts/
  synthesize` returned genuine, valid, playable WAV audio; a real
  `POST /webcam/session/demo/frames` → `GET .../summary` round-trip
  correctly computed a composite score *and* correctly flagged a real
  43-point confidence drop as a notable moment; the voice WebSockets and
  `/interview/personas`, `/interview/company-formats` were driven through
  real requests via Starlette's/FastAPI's TestClient. Phase 4's
  `SessionStateMachine` (13 tests), `PressureSimulator` (13), and
  `FrameworkDetector` (7), and Phase 5's confidence aggregation module
  (`compute_summary`, `detect_notable_moments`, `compute_baseline_
  comparison`, `downsample_frames` — 23 tests) are all pure logic with
  zero LLM/CV dependency — fully real, not mocked. The full interview HTTP
  flow (parse resume → parse JD → generate plan → create session → start
  → warm-up → answer → follow-up → completion → evaluations) is covered
  end to end in `test_interview_routes.py` with the LLM provider swapped
  for a scripted fake at the FastAPI dependency-injection boundary — a
  real request/response lifecycle through 15+ HTTP calls, just not a real
  model behind it.
- **Frontend**: 226/226 Vitest tests pass across 29 files; `tsc -b
  --noEmit` is clean; `eslint --max-warnings 0` is clean; `vite build`
  produces a working production bundle. Phase 4's XState
  `interviewMachine` (9 tests, including per-substate pause/resume) is
  pure state logic mirroring the backend's `SessionStateMachine` 1:1.
  Phase 5's `blinkDetector.ts` (the real Eye Aspect Ratio algorithm),
  `eyeContact.ts`, `headStability.ts`, `gestureAnalyzer.ts`,
  `expressionClassifier.ts`, and `confidenceCoach.ts` are all real
  geometry/signal-processing over synthetic MediaPipe-shaped landmark
  fixtures — 65+ tests, zero camera or ML model involved because none of
  it needs one. Two genuine bugs were caught and fixed while building
  these fixtures: a landmark-index collision where two independently-built
  synthetic eye regions silently overwrote each other's coordinates (real
  MediaPipe topology reuses those indices across sub-systems, so isolated
  fixtures have to compose, not just coexist), and a `vi.restoreAllMocks()`
  side effect that was wiping standalone mock return values, not just
  spies, between `WebcamCapture` tests.
- **Not yet compiled**: the Rust/Tauri shell (`src-tauri/`), including the
  OS-keychain BYOK module — no Rust toolchain was available in the
  scaffold environment. See note above.
- **Not exercised end-to-end**: real cloud provider calls (OpenAI/Anthropic/
  etc.), real Ollama model pulls, real Whisper/Piper/XTTS/Silero inference,
  real PDF/DOCX resume parsing *content quality*, and real MediaPipe Face
  Mesh/Pose inference (`FaceAnalyzer.processFrame` is written against the
  real API surface but throws in this build — see Phase 5 notes below) —
  no network route to those hosts from this sandbox, no camera/audio
  hardware, and multi-GB model weights aren't fetchable here. Every
  LLM-backed Phase 4 module is tested with the provider mocked at a clean
  seam (`ModelProviderRouter.chat`); every CV-backed Phase 5 signal
  extractor is tested by feeding it synthetic landmark coordinates
  directly, bypassing MediaPipe entirely — the orchestration and math
  around each are real and tested even though the upstream model/camera
  input isn't.

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

## Phase 3 architecture notes

- **The placeholder-tone TTS backend is load-bearing, not a stub.** Piper,
  XTTS-v2, and Edge TTS all need something this environment doesn't have
  (a binary, a multi-GB model download, or network access to Microsoft's
  endpoint), so `TTSEngine.synthesize_stream` always falls back to a real,
  valid, audible sine-wave WAV tone — scaled to the input text's estimated
  speech duration — instead of raising. That's what let the whole
  encode → stream → decode → schedule → barge-in-stop pipeline get built
  and tested for real, instead of being mocked at the TTS boundary. Wiring
  in a real backend later is a matter of implementing
  `_synthesize_with_real_backend` and `_list_*_voices`; the streaming
  contract around it doesn't change.
- **STT follows the opposite pattern on purpose.** There's no honest
  placeholder for "transcribe this audio" — a fake transcript would be
  actively misleading. So `WhisperSTT` raises `ModelNotAvailableError`
  with a clear, actionable message (which endpoint, which model, where to
  go fix it) the moment `faster-whisper` or its weights aren't available,
  and the `/voice/stt/stream` WebSocket forwards that as a JSON error
  frame instead of crashing the socket. This *is* the "graceful fallback…
  show clear message + download prompt" acceptance criterion, not a
  workaround for skipping it.
- **Two-stage VAD, one algorithm.** The browser-side AudioWorklet
  (`public/worklets/mic-processor.js`) and the backend's `EnergyVAD`
  (`app/services/vad.py`) both use the same RMS-energy + zero-crossing-rate
  math on purpose, so "fast client-side feedback" and "VAD status you could
  cross-check server-side" agree with each other. `SileroVAD` is written
  behind the same interface for a future, more accurate swap, but isn't
  used by default (it needs `torch` + a model download).
- **`TurnManager` takes explicit timestamps, not wall-clock timers.** Every
  transition (including the 300ms barge-in debounce) is driven by the
  `timestamp_ms` already present on VAD frames, which is what makes its
  16-test suite fully deterministic — no fake timers, no flakiness.

## Phase 4 architecture notes

- **Every LLM call lives behind `ModelProviderRouter.chat`, and every test
  mocks at exactly that seam.** Ingestion, planning, the warm-up chat, and
  answer evaluation/follow-up generation all go through the same
  dependency-injected provider — so swapping in a real, working LLM later
  touches zero test files; the orchestration around each call (JSON
  parsing, Pydantic validation, prompt construction referencing actual
  resume/JD content) is already exercised.
- **The framework detector is a real heuristic, not a stub for an LLM
  call.** Like Phase 3's placeholder TTS tone, `FrameworkDetector` uses
  genuine cue-phrase matching (situation/task/action/result) that produces
  real, checkable output today. It's intentionally conservative about
  what it claims to detect — see the module docstring for exactly what
  it can't distinguish (e.g. SOAR's "obstacle" framing vs. STAR).
- **The pressure simulator and state machine need no LLM at all.**
  "Is the answer short", "are we past 75% of the time budget", "what
  state can this session legally transition to next" are deterministic
  questions — Exam Mode's pressure techniques and the whole session
  lifecycle are 100% real, tested logic, independent of whether a model
  is even configured.
- **`InterviewSessionDetail` is a companion table, not new columns on
  `sessions`.** Same pattern as Phase 2's tier override — keeps the
  generic `Session` table mode-agnostic so Phase 7's IELTS mode isn't
  stuck with a pile of nullable interview-only columns.
- **The plan's question list is walked by `(section_index,
  question_index)` pointers on the session row**, not by re-deriving
  position from the conversation history — so resuming a paused session
  (or replaying `/interview/sessions/{id}` after a crash) doesn't depend
  on reconstructing where you were from free text.
- **A real test-isolation bug got caught and fixed while building this
  phase** — see the comment in `tests/conftest.py`'s `client` fixture.
  Importing an `app.*` exception class *inside* a test function body
  (rather than at module top level) can bind to a different reloaded
  module instance than the one actually raising it, since the fixture
  aggressively drops `app.*` from `sys.modules` for engine isolation.
  `pytest.raises(...)` then silently fails to match. Worth knowing before
  adding Phase 5+ tests.

## Phase 5 architecture notes

- **Raw video never leaves the browser, structurally, not just by
  policy.** The backend never defines a route that accepts an image —
  `ConfidenceFrame` (the only thing `/webcam/*` ever receives) is
  numbers and enum strings, not pixels. There's no code path by which a
  frame *could* reach the backend even by mistake.
- **The composite score's heuristics are honest, working substitutes for
  ML models this environment can't run — not approximations pretending
  to be the real thing.** `expressionClassifier.ts`'s mouth/eyebrow
  geometry stands in for the spec's trained FER model; `headStability.ts`'s
  three-landmark pose estimate stands in for a full 6DOF solvePnP fit.
  Both are real, checkable, and documented as heuristics in their own
  module docstrings — the same pattern as Phase 4's `FrameworkDetector`
  and Phase 3's placeholder TTS tone. Swapping in a trained model or a
  full pose solver later doesn't change any other module's interface.
- **The blink detector is not a heuristic stand-in — EAR is *the*
  standard lightweight algorithm**, not a fallback for something better.
  Same for the composite-score weighting and the notable-moment/baseline-
  comparison math: those are just arithmetic, real regardless of what
  feeds them.
- **`FaceAnalyzer` splits cleanly into a tested half and an untested
  half.** `analyzeLandmarks()` (given landmarks, produce a full analysis)
  is where all the real logic lives and 100% of the test coverage is.
  `processFrame()` (given a video frame, call MediaPipe to get landmarks)
  is a two-line real integration point that currently throws — it's the
  *only* thing in this phase resembling a stub, and it's exactly as small
  as the actual browser-dependent surface area.
- **The confidence overlay defaults to off.** `Shell.tsx` only requests
  camera access when the person explicitly clicks "Turn on confidence
  tracking" — no page silently starts capturing video.
- **Session linkage to Phase 4 is loose on purpose.** `/webcam/*`'s
  `session_id` isn't a foreign key to `interview_session_details` — Phase
  5's spec explicitly calls for running "in complete isolation with mock
  session data." `Shell.tsx` currently passes `sessionId: null` to
  `useConfidenceTracking`; wiring it to the active interview session id
  is a one-line change once that's wanted, not an architectural one.

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

## Acceptance criteria status (Phase 3 spec, §"Acceptance Criteria")

| Criterion | Status |
|---|---|
| Mic capture works with device selection; volume meter shows real-time level | Code complete; device enumeration + meter UI verified via Vitest (jsdom); real getUserMedia/speaker output unverified (no browser/audio hardware here) |
| VAD correctly detects speech start/end with <200ms latency | ✅ Logic verified — 30ms-per-frame `EnergyVAD` classifies synthetic tone/silence/noise fixtures correctly; "<200ms" is a latency claim about real audio hardware, not testable here |
| STT transcribes spoken English with >90% accuracy | Not verified — no Whisper model weights fetchable in this sandbox. Orchestration logic (chunking, word timestamps) is tested with the model mocked; accuracy is faster-whisper's property, not this codebase's |
| Streaming STT yields partial results within 500ms | Code complete (2s buffer windows, configurable); `is_partial` flagging verified; real-world timing unverified |
| TTS synthesizes text and plays audio through speakers | ✅ Verified — real, valid WAV bytes generated and played back via a real (mocked-AudioContext) scheduling pipeline; "through speakers" specifically requires a real browser, unverified here |
| Streaming TTS begins playback within 200ms of first chunk | Code complete — `TTSPlayback` starts scheduling the first decoded chunk immediately, no artificial wait; exact ms timing unverified outside a real browser |
| Barge-in: speaking during TTS stops playback and captures new speech | ✅ Verified — `TurnManager`'s barge-in debounce + `TTSPlayback.stop()` wiring covered by dedicated tests |
| Full round-trip speak→transcribe→respond→TTS→hear in <3s (Local Full) | Not verified — requires real STT model + real hardware timing |
| Audio recordings saved locally and correctly timestamped | ✅ Verified — real file I/O against tmp_path, manifest sorting, cross-session isolation |
| Graceful fallback if Whisper model not downloaded | ✅ Verified — this is the actual, real code path in this environment, not a simulated one |

## Acceptance criteria status (Phase 4 spec, §"Acceptance Criteria")

| Criterion | Status |
|---|---|
| Resume parsing extracts structured data with reasonable accuracy | Text extraction ✅ verified (real PDF/DOCX round-trip); LLM structuring accuracy unverified (no reachable LLM) — schema validation + error handling ✅ verified |
| Interview plan is genuinely tailored to resume + JD content | Prompt construction references actual resume/JD content (✅ verified via mocked-provider assertions); whether the *model's output* is well-tailored is unverified here |
| Session state machine handles all transitions without invalid states | ✅ Verified — 13 tests cover the full graph, follow-up loop, time-exceeded from every substate, and pause/resume per substate |
| Dynamic follow-ups reference specifics from the candidate's actual answer | Follow-up prompt includes the evaluator's identified gaps (✅ verified prompt content); follow-up *quality* depends on the model, unverified |
| Pressure techniques fire at appropriate, realistic moments (Exam Mode) | ✅ Verified — 13 tests cover every trigger, priority ordering, and max-use caps |
| Behavioral framework detection identifies STAR/SOAR/CAR components | ✅ Verified for the heuristic baseline — 7 tests against hand-written sample answers; an LLM-backed version would be more nuanced but isn't implemented |
| Multi-round interview day builds a sensible round/persona/time schedule | ✅ Verified — 10 tests across all 5 company formats, round-count limits, and time totals |
| Full Q&A loop runs end-to-end: warm-up → questions → follow-ups → completion | ✅ Verified — full HTTP integration test through 2 questions + a follow-up branch to session completion |
| Text fallback mode works without the voice pipeline | ✅ This is actually the *only* mode implemented in `InterviewRoom.tsx` today — voice integration (Phase 3's `useVoicePipeline`) isn't wired into the interview room yet; see handoff notes |
| Session resumes correctly after pause | State machine supports it (✅ per-substate pause/resume tested on both frontend and backend); no `/interview/sessions/{id}/pause` HTTP endpoint was built to expose it yet |

## Acceptance criteria status (Phase 5 spec, §"Acceptance Criteria")

| Criterion | Status |
|---|---|
| Webcam capture works with device selection at 30fps | Code complete (`WebcamCapture.ts`, mirrors Phase 3's `MicCapture`); real getUserMedia/frame-rate behavior unverified (no camera/browser here) |
| MediaPipe Face Mesh detects face, tracks 468 landmarks | Not implemented — `FaceAnalyzer.processFrame` throws in this build (no WASM/model route). Everything *downstream* of landmarks is real and tested |
| Eye contact direction correctly identified | ✅ Verified — 11 tests against synthetic iris/eye-corner coordinates covering all 5 directions + rolling ratio |
| Head stability score reflects actual movement | ✅ Verified — 12 tests distinguishing stable/nodding/shaking/fidgeting via variance analysis |
| Blink rate within ±3 of manual count over 1 minute | Algorithm ✅ verified (17 tests: EAR computation, 100-400ms genuine-blink window, BPM accumulation); real-world ±3 accuracy claim needs real recorded video, unverified |
| Expression classifier runs at 5fps without lag | Heuristic classification ✅ verified (8 tests); this is a heuristic, not the spec's trained FER model — see architecture notes; performance/fps unverified (no browser) |
| Confidence overlay renders smoothly during a session | Component ✅ verified (7 tests: gauge, indicators, minimize, clamping); real-time smoothness needs a browser, unverified |
| Timeline data persisted to SQLite and retrievable | ✅ Verified — real DB round-trip via `POST .../frames` → `GET .../timeline`, live-booted and curl'd |
| Zero raw video data in any API call or DB record | ✅ Verified by construction — see architecture notes; `ConfidenceFrameRecord`'s columns are numbers/strings, there's no code path for pixels |
| Works across lighting conditions | Not applicable to this build — no camera/lighting input exists here |
| Graceful handling when no face detected | `analyzeLandmarks` always returns a result if given landmarks; `processFrame`'s "no face" path returns null per its docstring, but isn't exercised (needs MediaPipe) |
| Micro-coaching tips (max 1/30s, Practice Mode) | ✅ Verified — 12 tests: cooldown enforcement, sustained-condition timers, priority ordering, reset |
| Gesture analysis (fidgeting, face-touching) | ✅ Verified — 10 tests covering all 5 hand-position classifications + frequency-based assessment |
| Baseline comparison (warm-up vs. interview delta) | ✅ Verified — 7 tests including all 3 recovery-pattern classifications, live-booted and curl'd |
| Progress tracking across 3+ sessions | ✅ Verified — `compute_progress`/`GET /webcam/progress` tested with multiple sessions; UI comparison chart not built (backend + data model ready) |

## Handoff notes for the next phases

- **Phase 4 follow-up work (not blocking, but worth knowing):** the interview
  room is text-only today. Wiring in Phase 3's `useVoicePipeline` (mic
  capture → STT stream → `submitAnswer` → TTS playback of the interviewer's
  message) into `InterviewRoom.tsx` is the natural next step once a real
  STT model is available — the hook and the room component are both
  already built, they just aren't connected to each other yet. There's
  also no `/interview/sessions/{id}/pause` HTTP endpoint exposing the
  state machine's pause/resume capability, and no closing-chat LLM message
  before a session reaches `completed` (it just transitions straight
  through).
- **Phase 6 (Coding Sandbox):** `InterviewConductor` and the session state
  machine are built to be extended, not replaced — a coding round would
  add a new `PlannedQuestion.source` value and a parallel evaluation path
  alongside `process_answer`, reusing the same follow-up/pressure hooks.
  Use `ModelRole.VISION` for screen/whiteboard reading — note it raises
  `ProviderError` on Local Lite, which has no VLM in its model plan.
- **Phase 7 (IELTS Speaking):** `WhisperSTT.transcribe_complete()` returns
  word-level timestamps in `TranscriptionSegment.words` — exactly the
  shape pronunciation scoring needs. `contracts/mocks/mock-persona.json`
  and `mock-interview-plan.json` are fixtures if useful for parallel
  development.
- **Phase 8 (Scoring & Progress):** `GET /interview/sessions/{id}/
  evaluations` is built and tested — it's your primary data source, giving
  every question/follow-up turn with its score and feedback. Call
  `get_router().get_cost_estimate()` for the session cost line in the
  report; `SessionAudioRecorder.load_manifest()` gives you the voice
  replay timeline; `GET /webcam/session/{id}/summary` gives you the
  `ConfidenceSummary` to fuse in, and `ConfidenceTimeline` has the data
  for a session replay overlay; `contracts/mocks/mock-scores.json` and
  `mock-confidence-timeline.json` are fixtures to build against meanwhile.
- **Phase 5 follow-up work (not blocking, but worth knowing):** the
  confidence overlay in `Shell.tsx` is wired with `sessionId: null` —
  connecting it to the active Phase 4 interview session id is what makes
  `/webcam/*` data actually tie back to a real interview rather than
  floating unattached. `FaceAnalyzer.processFrame`'s real MediaPipe
  integration is the other open item; `analyzeLandmarks()` is ready and
  waiting for it.
- **Phase 10 (Motivation Engine):** `ConfidenceSummary.notable_moments`
  identifies specific timestamps where confidence dropped — use this for
  targeted practice suggestions. `GET /webcam/progress` already computes
  the before/after comparison data across sessions; only the UI chart
  (Phase 5 spec §5.13) isn't built yet.
