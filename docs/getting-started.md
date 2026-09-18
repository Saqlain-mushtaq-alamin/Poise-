# Getting Started with Poise

## 1. Download

Grab the installer for your platform from the [Releases page](https://github.com/saqlain/poise/releases):

| Platform | File |
|---|---|
| Windows 10/11 | `Poise_x.y.z_x64-setup.exe` (or the `.msi`) |
| macOS (Apple Silicon) | `Poise_x.y.z_aarch64.dmg` |
| macOS (Intel) | `Poise_x.y.z_x64.dmg` |
| Linux (Ubuntu 22.04+) | `Poise_x.y.z_amd64.AppImage` or `.deb` |

## 2. Install

- **Windows** — run the `.exe`, approve the UAC prompt. The installer is signed, so you should not see a SmartScreen warning.
- **macOS** — open the `.dmg`, drag Poise into Applications. The app is signed and notarized, so Gatekeeper should let it open normally.
- **Linux (AppImage)** — `chmod +x Poise_*.AppImage && ./Poise_*.AppImage`
- **Linux (.deb)** — `sudo dpkg -i poise_*.deb`

## 3. First run

On first launch, the **setup wizard** walks you through:

1. A hardware scan (CPU/RAM/GPU) that recommends a tier
2. Confirming or overriding that tier
3. Downloading local models (Local tiers) or connecting an API key (Cloud tier)
4. A microphone and speaker check
5. An optional camera check
6. A 60-second demo interview so you can see a sample report

You can skip any step and finish it later from **Settings → Setup**.

## 5. Next Steps & Documentation

- 📖 Detailed feature manual → [`user-guide.md`](./user-guide.md)
- 🖥️ Hardware tier setup → [`hardware-guide.md`](./hardware-guide.md)
- 🏛️ Technical Architecture → [`architecture.md`](./architecture.md)
- 💻 Developer setup & compilation → [`developer-guide.md`](./developer-guide.md)
- 🔌 API Reference → [`api-reference.md`](./api-reference.md)
- 🧪 Testing & Quality Control → [`testing-and-qc.md`](./testing-and-qc.md)

## 6. Troubleshooting

- GPU/driver issues → [`gpu-troubleshooting.md`](./gpu-troubleshooting.md)
- API key issues → [`api-key-setup.md`](./api-key-setup.md)
- Everything else → [`faq.md`](./faq.md)

## 7. Updates

Poise checks for updates automatically on launch. When one is found you'll see a banner at the top of the app — click **Download & install**, then **Restart now** when it's ready. Updates are cryptographically signed and verified before install.
