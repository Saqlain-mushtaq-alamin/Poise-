# 📖 User Guide — Poise

Welcome to **Poise**! This step-by-step guide will walk you through setting up, configuring, and getting the most out of your AI interview and IELTS speaking practice.

---

## 1. Installation & First-Run Setup

### 1.1 Downloading Poise
Get the latest installer for your operating system from the official Releases page:
- **Windows:** Download `Poise_Setup.exe` (or `.msi`)
- **macOS:** Download `Poise_aarch64.dmg` (Apple Silicon) or `Poise_x64.dmg` (Intel)
- **Linux:** Download `Poise_amd64.AppImage` or `.deb`

### 1.2 First-Run Setup Wizard
On launching Poise for the first time, the **Setup Wizard** will automatically guide you through:
1. **Hardware Detection:** Poise scans your GPU, CPU cores, and System VRAM/RAM to recommend a Hardware Tier.
2. **Provider Selection:** Choose whether to use **Local Models (Ollama)** or **Cloud AI (BYOK - Bring Your Own Key)**.
3. **Microphone & Speaker Check:** Verify your audio input levels and playback.
4. **Webcam Calibration:** Optionally verify camera framing for facial confidence tracking.
5. **Quick Demo:** Run a 60-second trial session to explore the interface.

---

## 2. Configuring AI Providers & Models

Navigate to **Settings → Provider** inside Poise to manage model backends:

### 2.1 Local Inference (Ollama)
1. Install [Ollama](https://ollama.com) on your computer.
2. Pull your preferred model via command line:
   ```bash
   ollama pull llama3.1:8b   # Recommended for High Tier
   ollama pull qwen2.5:7b    # Recommended for Coding / Technical
   ollama pull phi3:mini     # Recommended for Mid/Low Tier
   ```
3. In Poise, select **Local (Ollama)** as your active provider. Poise will automatically detect installed models.

### 2.2 Cloud Inference (BYOK — Bring Your Own Key)
If you prefer fast, cloud-based AI:
1. Select your preferred provider (**OpenAI**, **Anthropic**, **Google Gemini**, **Groq**, or **DeepSeek**).
2. Enter your API key.
3. Your key is stored securely in your OS Keychain (Windows Credential Manager / macOS Keychain). Plain-text keys are never written to disk.

---

## 3. Practice Modes

### 🎙️ Mode 1: Job Interview Practice

1. **New Session:** Click **Start Interview** on the Dashboard.
2. **Upload Artifacts:**
   - **Resume:** Drag and drop your `.pdf` or `.docx` resume.
   - **Job Description (JD):** Paste the job posting text or target role details.
3. **Configure Session:**
   - **Duration:** 15m, 30m, 45m, or 60m.
   - **Rounds to Include:** Behavioral (STAR method), Technical/System Design, Sandboxed Coding.
   - **Interviewer Persona:** Professional, Friendly, Strict, or Pressure-test.
4. **Live Interview:**
   - Listen to the AI interviewer prompt you.
   - Speak naturally — Poise uses Voice Activity Detection (VAD) to recognize when you finish speaking.
   - Use the **Coding Editor** during coding sections to write and run Python solutions against test cases.
5. **Review Report:** After completion, review your **Fused Performance Score**, radar charts, filler word frequency, and question-by-question model answer comparisons.

---

### 🇬🇧 Mode 2: IELTS Speaking Practice

1. **Start IELTS Test:** Click **IELTS Mode** from the main menu.
2. **Select Topic / Random Test:** Choose a specific IELTS topic or let Poise generate an authentic test card.
3. **Test Flow:**
   - **Part 1 (Introduction):** Answer 4-5 quick questions about daily life, work, or hobbies.
   - **Part 2 (Cue Card):** Receive a topic card. You get **60 seconds** to take notes, followed by a **2-minute uninterrupted speech**.
   - **Part 3 (Discussion):** Engage in a multi-turn deep discussion on abstract concepts connected to Part 2.
4. **Band Evaluation:** Receive immediate band scores (1.0 – 9.0) across *Fluency & Coherence*, *Lexical Resource*, *Grammatical Accuracy*, and *Pronunciation*, alongside detailed improvement suggestions.

---

## 4. Diagnostic Reports & History

- **Session History:** Access all past practice logs under **History**.
- **PDF Export:** Click **Export PDF** on any completed session report to download a publication-ready PDF evaluation document.
- **Analytics & Trends:** Track your speech pace (WPM), confidence stability, and IELTS band score trajectory over time.
