# FAQ

**Do I need an internet connection?**
Only for Cloud Assist and for downloading models the first time on a Local tier. Once models are downloaded, Local Lite and Local Full work fully offline.

**Where is my data stored?**
Locally, in a SQLite database on your machine. See [`privacy.md`](./privacy.md) for the full breakdown of what goes where.

**Can I switch tiers later?**
Yes, any time from Settings → Tier. Nothing from the wizard locks you in.

**The app won't open on macOS ("unidentified developer").**
This shouldn't happen with a signed, notarized release — if you see it, you may have downloaded a build from an untrusted source, or Gatekeeper's cache is stale. Try `xattr -d com.apple.quarantine /Applications/Poise.app` and reopen, or re-download from the official Releases page.

**Windows shows a SmartScreen warning.**
Signed releases shouldn't trigger this. If it happens, verify you downloaded from the official GitHub Releases page and not a mirror.

**How do updates work?**
Poise checks a signed update manifest on launch (non-blocking). If a newer version is available you'll see a banner; installing downloads and verifies the signature before applying it, and a restart completes the update.

**What happens if my GPU runs out of memory mid-session?**
You'll see "Not enough GPU memory — try closing other apps." Your session progress up to that point is saved; see [`gpu-troubleshooting.md`](./gpu-troubleshooting.md).

**Is crash reporting on by default?**
No — it's opt-in, off by default, and strips personal data before sending (Settings → Privacy → Crash Reporting).

**Can I use Poise without a microphone or camera?**
Yes. Text mode works fully without either; skip those steps in the wizard.

**How do I redo the setup wizard?**
Settings → Setup → "Redo setup".
