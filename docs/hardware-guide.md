# Hardware Guide

Poise runs in one of three tiers. The setup wizard scans your machine and recommends one, but you can override it any time in **Settings → Tier**.

## Cloud Assist

- **Requirements:** any machine, internet connection, an API key from OpenAI, Anthropic, or Google (BYOK — bring your own key)
- **What runs where:** all model calls go to your chosen provider; nothing large downloads to your machine
- **Best for:** low-spec machines, laptops, or anyone who wants the highest-quality models without managing local downloads
- **Cost:** pay-as-you-go to your provider. Poise defaults to a soft cap of 50K tokens/session with a ~$2 estimate warning before you exceed it — you can raise this per-session.

## Local Lite

- **Requirements:** 8 GB+ RAM, any modern CPU, GPU optional
- **What runs where:** a small local model runs fully offline
- **Best for:** practicing without an internet connection or API key, on modest hardware
- **Trade-off:** lower response quality than Local Full or Cloud

## Local Full

- **Requirements:** NVIDIA GPU with 8 GB+ VRAM recommended, 16 GB+ system RAM
- **What runs where:** the full local model set runs on your GPU, fully offline
- **Best for:** highest-quality fully offline practice
- **Trade-off:** larger downloads (several GB), needs a capable GPU

## Why was tier X recommended?

The hardware scan checks:

- **GPU presence + VRAM** — no GPU or <6 GB VRAM steers you toward Cloud or Local Lite
- **System RAM** — under 8 GB rules out Local Full
- **CUDA availability** — Local Full requires a working NVIDIA/CUDA setup (see [`gpu-troubleshooting.md`](./gpu-troubleshooting.md) if this fails to detect)

You can always switch tiers later — nothing is locked in after setup.
