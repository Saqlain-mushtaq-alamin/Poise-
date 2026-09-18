# 💻 Developer & Setup Guide — Poise

This guide provides instructions for developers looking to set up, build, test, and contribute to **Poise**.

---

## 1. Monorepo Structure

```
Poise-/
├── backend/            # FastAPI Python 3.11 sidecar engine
│   ├── app/
│   │   ├── main.py     # Entrypoint (finds free port, prints POISE_SIDECAR_PORT)
│   │   ├── config.py   # Pydantic environment configuration
│   │   ├── database.py # SQLAlchemy engine & SQLite session setup
│   │   ├── models/     # ORM models (InterviewSession, IELTS, Scoring, etc.)
│   │   ├── routers/    # REST API endpoints (/health, /interview, /voice, etc.)
│   │   ├── schemas/    # Pydantic request/response schemas
│   │   └── services/   # Business logic (planner, fusion, ingestion, provider)
│   ├── alembic/        # Database migration scripts
│   ├── requirements.txt
│   └── tests/          # Pytest backend test suite
├── frontend/           # React 18 + TypeScript + Vite UI app
│   ├── src/
│   │   ├── components/ # Modular UI components
│   │   ├── hooks/      # Custom React hooks (useAudioRecorder, useSidecar, etc.)
│   │   ├── pages/      # Views (Dashboard, Interview, IELTS, Reports, Settings)
│   │   └── services/   # API client and sidecar RPC bridge
│   ├── package.json
│   └── vite.config.ts
├── src-tauri/          # Tauri v2 Rust desktop shell
│   ├── src/
│   │   ├── main.rs     # Rust app entrypoint
│   │   ├── sidecar.rs  # Sidecar process manager & port parser
│   │   └── keytar.rs   # OS keychain bindings
│   ├── Cargo.toml
│   └── tauri.conf.json
├── contracts/          # OpenAPI/TypeScript shared type definitions
├── docs/               # Project documentation suite
└── tests/              # Root integration & system test suite
```

---

## 2. Prerequisites

- **Node.js:** v18.0 or higher
- **npm:** v9.0 or higher
- **Python:** 3.11.x
- **Rust Toolchain:** `rustc` and `cargo` 1.75+ (for Tauri builds)
- **C++ Build Tools:** Visual Studio C++ Build Tools (Windows) or Xcode Command Line Tools (macOS)

---

## 3. Local Development Setup

### 3.1 Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Launch backend standalone
python -m app.main
```
The backend will print `POISE_SIDECAR_PORT=<port>` to stdout and start listening on `127.0.0.1:<port>`.

### 3.2 Frontend Setup
```bash
cd frontend

# Install Node modules
npm install

# Run Vite development server
npm run dev
```
Open `http://localhost:5173` in your browser.

### 3.3 Running Tauri App in Dev Mode
```bash
# From workspace root or frontend/
npm run tauri dev
```
This compiles the Rust shell, starts Vite, launches the Python sidecar, and opens the native application window.

---

## 4. Production Packaging & Sidecar Compilation

Building a production distribution requires compiling the Python backend into a single executable sidecar binary using PyInstaller.

1. **Compile Backend Sidecar Binary:**
   ```bash
   cd backend
   python scripts/build_sidecar.py
   ```
   This creates `src-tauri/binaries/poise-backend-x86_64-pc-windows-msvc.exe` (or host target tuple).

2. **Build Production Desktop Package:**
   ```bash
   cd frontend
   npm run tauri build
   ```
   Tauri will bundle the frontend assets, executable sidecar, and Rust shell into an installer executable (`.exe`, `.msi`, `.dmg`, or `.AppImage`).

---

## 5. Running Quality Control & Test Suites

Always run the full QC verification suite before submitting pull requests:

```bash
# 1. Run all backend Python tests
cd backend
$env:PYTHONPATH="backend"; .\.venv\Scripts\pytest backend/tests
$env:PYTHONPATH="backend"; .\.venv\Scripts\pytest tests

# 2. Run frontend TypeScript & Lint check
cd frontend
npm run build

# 3. Verify Rust desktop shell compilation
cd src-tauri
cargo check
```
