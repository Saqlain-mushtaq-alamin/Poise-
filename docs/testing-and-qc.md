# 🧪 Testing & Quality Control (QC) Report — Poise

This document details the Quality Control methodology, test suite execution metrics, bug fixes, and verification results for **Poise**.

---

## 1. Quality Control Overview

Poise implements a multi-layered verification strategy across backend Python micro-services, frontend React components, and the Rust desktop shell.

```
┌────────────────────────────────────────────────────────┐
│                   Quality Control Layers                │
├────────────────────────────────────────────────────────┤
│ 1. Backend Unit & Integration Tests (pytest)            │
│ 2. Schema & Structure Validation (Pydantic / LiteLLM)  │
│ 3. Frontend Static Type Check & Build (tsc / Vite)    │
│ 4. Rust Desktop Shell Verification (cargo check)       │
└────────────────────────────────────────────────────────┘
```

---

## 2. Test Execution Summary

| Test Layer | Framework / Tool | Scope | Results | Status |
|---|---|---|---|---|
| **Backend Core** | Pytest (`pytest 8.4.2`) | Routers, State Machines, Audio, Hardware, Fusion, Ingestion, Sandbox, Providers | **300 Passed**, 1 Skipped | 🟢 **PASS (100%)** |
| **Root Integration** | Pytest | Score Fusion, Answer Annotator, Coverage Matrix, Readiness, Playbooks, PDF Export | **43 Passed**, 0 Failures | 🟢 **PASS (100%)** |
| **Frontend UI** | TypeScript Compiler (`tsc`) & Vite | React 18, State Management, UI Components, Tailwind CSS | **1149 Modules Built** (0 Errors) | 🟢 **PASS (100%)** |
| **Desktop Shell** | Cargo (`cargo check`) | Tauri v2 Process Manager, Sidecar Launcher, OS Keytar | **0 Compilation Errors** | 🟢 **PASS (100%)** |

---

## 3. Bug Fixes & Code Enhancements Applied During QC

During Quality Control auditing, the following issues were identified and resolved:

### 1. Missing Dependency Resolution (`reportlab`)
- **Issue:** PDF export test (`test_pdf_export.py`) failed due to missing `reportlab` library in backend environment.
- **Fix:** Installed `reportlab 5.0.1` and added requirement constraint `reportlab>=4.0.0` to `backend/requirements.txt`.

### 2. Defensive Object Handling in Score Fusion Engine (`fusion.py`)
- **Issue:** Mock/fake adapters without a `.db` property raised `AttributeError` when `get_persona_and_jd` checked `if self.db is None:`.
- **Fix:** Updated check in `backend/app/services/scoring/fusion.py` to use `if getattr(self, "db", None) is None:`, enabling seamless custom adapter testing.

### 3. Schema & Type Validation Resilience (`ingestion.py` & `planner.py`)
- **Issue:** Schema mismatch tests in `test_ingestion.py` and `test_planner.py` failed when malformed or non-list LLM payloads caused unhandled `TypeError`/`AttributeError`.
- **Fix:** Enhanced type checking and exception handling in `ResumeParser` and `InterviewPlanner` to catch `TypeError`, `AttributeError`, and `JSONDecodeError`, converting them into explicit `StructuringError` and `PlanGenerationError`.

---

## 4. Verification Commands

To re-run and verify the quality suite on any environment:

```bash
# 1. Run Python Backend Test Suites
cd backend
$env:PYTHONPATH="backend"; .\.venv\Scripts\pytest backend/tests
$env:PYTHONPATH="backend"; .\.venv\Scripts\pytest tests

# 2. Run Frontend Build & Type Verification
cd frontend
npm run build

# 3. Verify Rust Desktop Shell
cd src-tauri
cargo check
```
