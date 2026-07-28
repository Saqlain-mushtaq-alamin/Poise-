# Privacy Architecture

Poise is a local-first app. This page is a precise account of what data goes where.

## Stored locally, never leaves your machine

- Session recordings, transcripts, scores, and history — SQLite database in your OS's app-data directory
- Webcam confidence-signal analysis (posture, eye contact) — processed frame-by-frame in memory; **no video is ever written to disk or sent anywhere**
- API keys — OS keychain (Windows Credential Manager / macOS Keychain / Linux Secret Service), never a plaintext file

## Sent over the network (only with your consent / choice)

| Data | Sent to | When |
|---|---|---|
| Your interview answers/questions (text) | Your chosen provider (OpenAI/Anthropic/Google) | Only if you selected **Cloud Assist** and only for the duration of that API call |
| Crash reports (PII-stripped: error category, stack trace, app version — never session content) | Sentry | Only if you've opted in via Settings → Privacy → Crash Reporting (off by default) |
| Update manifest check (app version) | GitHub Pages (static file, no request logging beyond standard GitHub infra) | On every app launch, non-blocking |

## Local tiers (Local Lite / Local Full)

No interview content ever leaves your machine. Model inference happens entirely on your CPU/GPU via a locally-run Ollama process bound to `127.0.0.1` only — it is not reachable from your network.

## Sidecar network exposure

The FastAPI sidecar that the frontend talks to binds exclusively to `127.0.0.1` on a randomly chosen port at each launch. It is never exposed on `0.0.0.0` and is not reachable from other devices on your network.

## Deleting your data

Settings → Data → **Delete all local data** removes the SQLite database, cached models, and any stored keys. This is irreversible.

## Questions

Open an issue on the [GitHub repo](https://github.com/saqlain/poise) or see [`faq.md`](./faq.md).
