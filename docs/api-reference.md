# 🔌 API Reference — Poise Local Sidecar Engine

The embedded **FastAPI Local Engine** exposes REST API endpoints on `127.0.0.1:<port>`. The frontend communicates with these endpoints over localhost HTTP and WebSocket connections.

---

## 1. System & Health Endpoints

### `GET /health`
Returns the status of the local sidecar engine.
- **Response `200 OK`:**
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "environment": "development"
  }
  ```

---

## 2. Hardware & Tier Discovery

### `GET /hardware/scan`
Triggers a system hardware scan (CPU cores, RAM, NVIDIA/Apple Silicon GPU VRAM) and returns a recommended hardware tier.
- **Response `200 OK`:**
  ```json
  {
    "tier": "high",
    "cpu_cores": 12,
    "total_ram_gb": 32.0,
    "gpu_name": "NVIDIA GeForce RTX 4070",
    "vram_gb": 12.0,
    "recommended_provider": "ollama",
    "recommended_models": ["llama3.1:8b", "qwen2.5:7b"]
  }
  ```

---

## 3. Model Provider Configuration

### `GET /provider/status`
Returns active AI model provider status and available local/cloud models.

### `POST /provider/test`
Validates connectivity for a specific provider (e.g., Ollama or cloud API key).
- **Request Body:**
  ```json
  {
    "provider_type": "ollama",
    "api_key": null,
    "base_url": "http://localhost:11434"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "success": true,
    "models": ["llama3.1:8b", "qwen2.5:7b", "phi3:mini"]
  }
  ```

---

## 4. Interview Practice Management

### `POST /interview/ingest`
Ingests a candidate's resume (PDF/DOCX) and target Job Description.
- **Form Data:**
  - `resume_file`: Binary file upload (`.pdf` or `.docx`)
  - `jd_text`: String text of the job description
- **Response `200 OK`:** Returns structured `ResumeData` and `JobDescription` objects.

### `POST /interview/plan`
Generates a structured, time-budgeted interview plan.
- **Request Body:**
  ```json
  {
    "duration_minutes": 45,
    "include_behavioral": true,
    "include_technical": true,
    "include_coding": true,
    "difficulty": "medium",
    "persona": "professional"
  }
  ```

### `POST /interview/session/start`
Starts an interview session and initializes state machine `InterviewConductor`.

### `POST /interview/turn`
Processes a candidate answer turn and returns the interviewer's voice/text response.

---

## 5. IELTS Speaking Assessment

### `POST /ielts/session/start`
Initializes a new IELTS Speaking session (Part 1, Part 2, or Part 3).

### `POST /ielts/part2/cue-card`
Generates an authentic IELTS Part 2 Cue Card prompt.

### `POST /ielts/evaluate`
Generates band scores (1.0 - 9.0) and criteria breakdown for an IELTS session.

---

## 6. Sandboxed Coding & IDE

### `POST /coding/execute`
Runs Python code inside a sandboxed runner against unit tests.
- **Request Body:**
  ```json
  {
    "code": "def two_sum(nums, target):\n    ...",
    "test_cases": [
      {"input": "nums = [2,7,11,15], target = 9", "expected": "[0, 1]"}
    ]
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "passed": true,
    "total_tests": 1,
    "passed_tests": 1,
    "stdout": "",
    "execution_time_ms": 42
  }
  ```

---

## 7. Speech & Audio Endpoints

### `POST /voice/stt`
Transcribes uploaded PCM/WAV audio blob into text using `faster-whisper`.

### `POST /voice/tts`
Synthesizes text into spoken audio using `edge-tts` or `piper`. Returns WAV/MP3 audio payload.

---

## 8. Scoring & Diagnostic Reports

### `GET /scoring/report/{session_id}`
Returns fused performance report, breakdown by dimension (Content, Confidence, Coding, Communication), and PDF export download link.
