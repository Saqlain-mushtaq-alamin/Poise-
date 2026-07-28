# GPU Troubleshooting

Applies to the **Local Lite** and **Local Full** tiers, which run models on your GPU via Ollama.

## "Not enough GPU memory" errors

This maps to the `GPU_OUT_OF_MEMORY` error category. Try, in order:

1. Close other GPU-heavy apps (browsers with many tabs, games, other AI tools).
2. Switch to **Local Lite** in Settings → Tier — it uses a smaller model footprint.
3. If you're on the edge of a VRAM threshold, switching to **Cloud Assist** removes local GPU load entirely.

## NVIDIA driver issues

1. Confirm your driver is installed and current: `nvidia-smi` should print your GPU and driver version.
2. If `nvidia-smi` isn't found, install/update drivers from [nvidia.com/drivers](https://www.nvidia.com/drivers).
3. Restart after a driver update — Poise re-scans hardware on next launch.

## CUDA not detected

- Poise bundles the CUDA runtime it needs via Ollama — you don't need to install the CUDA Toolkit separately.
- If the hardware scan reports "CUDA unavailable" but `nvidia-smi` works, check that no other process (e.g. an exclusive-mode game) is holding the GPU.
- WSL2 users: make sure you're on a WSL2 kernel with GPU passthrough enabled (`wsl --update`), not WSL1.

## Ollama setup issues

- Poise manages its own Ollama subprocess — you don't need a separate Ollama install.
- If model downloads stall or fail repeatedly, check disk space (`Local Full` needs several GB free) and that outbound HTTPS isn't blocked by a firewall/proxy.
- Logs: `%APPDATA%\poise\logs\ollama.log` (Windows) or `~/Library/Application Support/poise/logs/ollama.log` (macOS) or `~/.local/share/poise/logs/ollama.log` (Linux).

## Still stuck?

Re-run the hardware scan from **Settings → Setup → Redo setup**, and see [`faq.md`](./faq.md). If you opted into crash reporting, error details are also sent to help us diagnose patterns across users — never any personal or session content.
