# 🎯 Poise — Privacy-First AI Interview & IELTS Speaking Coach

> **Master high-stakes job interviews and IELTS speaking tests on your own hardware — zero subscription, zero cloud lock-in, zero data leakage.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![Tauri](https://img.shields.io/badge/Tauri-v2-orange.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)
![React](https://img.shields.io/badge/React-18-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-yellow.svg)

---

## 🌟 Overview

**Poise** is an installable, cross-platform desktop application designed to provide unlimited, realistic practice for technical/behavioral job interviews and IELTS speaking assessments. 

Unlike proprietary web platforms that charge monthly subscriptions or cap session usage, Poise runs **local AI inference** directly on your GPU/CPU via [Ollama](https://ollama.com) or supports Bring-Your-Own-Key (BYOK) cloud endpoints (OpenAI, Anthropic, Gemini, Groq, DeepSeek). Your video, voice, resume, and code never leave your machine unless explicitly directed through your own API keys.

---

## 🚀 Key Features

### 🎙️ 1. Persona-Driven Voice Interviews
- **Realistic Voice Loop:** Natural conversation flow with Speech-to-Text (`faster-whisper`), low-latency Text-to-Speech (`edge-tts` / `piper`), and Voice Activity Detection (VAD).
- **Tailored Question Planning:** Parses your Resume (PDF/DOCX) and Target Job Description (JD) to construct role-specific behavioral and technical questions.
- **Dynamic Follow-ups & Interruption:** AI interviewers react naturally, probing deeper into unclear answers or adapting to your pace.

### 🇬🇧 2. IELTS Speaking Band Evaluator
- **Full Test Simulation:** Covers Part 1 (Introduction & Familiar Topics), Part 2 (Cue Card 2-minute speech), and Part 3 (Two-way Discussion).
- **Descriptive Band Feedback:** Provides detailed breakdowns against official IELTS criteria: *Fluency & Coherence*, *Lexical Resource*, *Grammatical Range & Accuracy*, and *Pronunciation*.

### 💻 3. Technical & Sandboxed Coding Rounds
- **Sandboxed Execution:** Evaluates Python code submissions in isolated subprocess or Docker environments.
- **Multimodal Screen & Code Feedback:** Evaluates logic, time complexity, edge cases, and code readability using LLMs and vision-language capabilities.

### 📹 4. Webcam & Multi-Modal Confidence Scoring
- **MediaPipe Facial Signal Analysis:** Evaluates non-verbal cues (eye contact, head movement stability, expression variance, blink rate).
- **Fused Performance Score:** Combines content relevance, delivery confidence, communication pace, and code quality into unified radar charts and actionable diagnostic reports.

### 🔒 5. Privacy & Zero-Hosting Architecture
- **100% Local Inference Support:** Run small, fast local LLMs (Llama 3, Qwen 2.5, Phi-3, Mistral) on your own device.
- **BYOK (Bring Your Own Key):** Unified model routing via LiteLLM to use cloud models at cost without intermediate servers.
- **Local Persistence:** All sessions, audio logs, transcripts, and reports are saved to a local SQLite database and optional local vector store.

---

## 🏗️ System Architecture

Poise uses a lightweight **Tauri Desktop Shell** (Rust) paired with an embedded **FastAPI Local Engine** spawned as a sidecar process on an OS-assigned free port.

```
┌──────────────────────────────────────────────────────────────────┐
│                      POISE DESKTOP APP (Tauri)                   │
│                                                                  │
│  ┌────────────────────┐        ┌─────────────────────────────┐   │
│  │  Frontend (React,   │◄──────►│  FastAPI Sidecar Process    │   │
│  │  Vite, Tailwind,   │  IPC   │  (Python 3.11 engine)       │   │
│  │  MediaPipe VAD)    │        │  State Machine & LiteLLM    │   │
│  └────────────────────┘        └───────────────┬─────────────┘   │
│                                                │                 │
│                    ┌───────────────────────────┼─────────────┐   │
│                    ▼                           ▼             ▼   │
│         ┌────────────────────┐     ┌─────────────────┐ ┌───────┐ │
│         │ Model Router       │     │ Speech Layer    │ │Vision │ │
│         │ (LiteLLM)          │     │ faster-whisper  │ │Media- │ │
│         │ ├─ Local (Ollama)  │     │ edge-tts/piper  │ │Pipe   │ │
│         │ └─ Cloud (BYOK)    │     └─────────────────┘ └───────┘ │
│         └────────────────────┘     ┌─────────────────┐           │
│                                    │ Sandbox & SQLite│           │
│                                    │ Docker/Subproc  │           │
│                                    └─────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

For detailed architectural specs, see [`docs/architecture.md`](./docs/architecture.md) and [`docs/how-it-works.md`](./docs/how-it-works.md).

---

## ⚙️ Hardware Tiers

Poise automatically scans your machine's CPU, RAM, and GPU on first run to recommend an optimal tier:

| Tier | Minimum Specs | Recommended LLM Provider / Models |
|---|---|---|
| **Ultra** | RTX 3080/4080 (16GB+ VRAM) or Apple M1/M2/M3 Max | Local Qwen 2.5 14B/32B or Llama 3.1 70B (Ollama) |
| **High** | RTX 3060/4060 (8GB-12GB VRAM) or Apple M1/M2/M3 Pro | Local Llama 3.1 8B or Qwen 2.5 7B (Ollama) |
| **Mid** | 16GB System RAM + i7/Ryzen 7 (Integrated/Entry GPU) | Local Phi-3 / Qwen 2.5 3B or BYOK Cloud (Groq/OpenAI) |
| **Cloud / Low** | 8GB System RAM (Low Spec Laptop) | Cloud BYOK (OpenAI GPT-4o-mini, Groq Llama 3, Gemini Flash) |

See [`docs/hardware-guide.md`](./docs/hardware-guide.md) for full configuration options.

---

## 📦 Quick Start Guide

### Prerequisites
- **Node.js** v18+ and **npm** v9+
- **Python** 3.11+
- **Rust toolchain** (if building Tauri app binary from source)
- *(Optional)* [Ollama](https://ollama.com) installed for 100% offline local inference.

### Development Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/saqlain-mushtaq-alamin/Poise-.git
   cd Poise-
   ```

2. **Setup Backend Environment:**
   ```bash
   cd backend
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Setup Frontend Environment:**
   ```bash
   cd frontend
   npm install
   ```

4. **Run in Development Mode:**
   - **Backend Engine:**
     ```bash
     cd backend
     python -m app.main
     ```
   - **Frontend UI (Vite Dev Server):**
     ```bash
     cd frontend
     npm run dev
     ```
   - **Full Tauri Desktop App:**
     ```bash
     npm run tauri dev
     ```

---

## 🧪 Testing & Quality Control

Poise maintains a robust test suite covering backend API routes, LLM prompt engineering, audio processing, sandbox execution, and front-end builds.

```bash
# Run backend Python tests (300+ tests)
cd backend
python -m pytest backend/tests tests

# Run frontend TypeScript build verification
cd frontend
npm run build

# Verify Rust Tauri Shell
cd src-tauri
cargo check
```

See [`docs/testing-and-qc.md`](./docs/testing-and-qc.md) for full test metrics and Quality Control reports.

---

## 📚 Documentation Index

Detailed guides are located in the [`docs/`](./docs) folder:

- 🚀 [Getting Started Guide](./docs/getting-started.md)
- 📖 [User Guide](./docs/user-guide.md)
- 🏛️ [System Architecture](./docs/architecture.md)
- ⚙️ [Technical How-It-Works](./docs/how-it-works.md)
- 💻 [Developer & Build Guide](./docs/developer-guide.md)
- 🔌 [API Reference](./docs/api-reference.md)
- 🖥️ [Hardware & Tier Guide](./docs/hardware-guide.md)
- 🔒 [Privacy & Security](./docs/privacy.md)
- 🔧 [GPU Troubleshooting](./docs/gpu-troubleshooting.md)
- 🧪 [Testing & QC Report](./docs/testing-and-qc.md)
- ❓ [FAQ](./docs/faq.md)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
