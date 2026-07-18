"""Hardware detection.

Probes the host machine for what Poise needs to pick a sane default tier:
GPU (vendor + VRAM), system RAM, CPU, and the optional local tooling
(Docker, Ollama) that unlocks the fuller local tiers.

Every probe is best-effort and individually fails soft — a missing
`nvidia-smi`, a Docker daemon that isn't running, or a slow network call
should degrade the profile, never crash detection. Each subprocess call is
given a short timeout so one hung tool can't stall the whole first-run
wizard.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field

import httpx
import psutil

SUBPROCESS_TIMEOUT_SECONDS = 3.0
OLLAMA_TIMEOUT_SECONDS = 2.0
DOCKER_TIMEOUT_SECONDS = 2.0
OLLAMA_BASE_URL = "http://localhost:11434"


@dataclass
class GPUInfo:
    name: str
    vram_total_mb: int
    vram_available_mb: int
    driver: str  # "nvidia" | "amd" | "apple" | "intel"
    compute_capability: str | None = None


@dataclass
class HardwareProfile:
    os: str  # "windows" | "macos" | "linux"
    cpu_cores: int
    cpu_name: str
    ram_total_gb: float
    ram_available_gb: float
    gpus: list[GPUInfo] = field(default_factory=list)
    docker_available: bool = False
    ollama_available: bool = False
    ollama_models: list[str] = field(default_factory=list)


# ---- Individual probes (each one is independently swappable/mockable) ----


def _detect_os() -> str:
    import platform

    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def _detect_cpu() -> tuple[int, str]:
    import platform

    cores = psutil.cpu_count(logical=True) or 1
    name = platform.processor() or platform.machine() or "unknown"
    return cores, name


def _detect_ram() -> tuple[float, float]:
    vm = psutil.virtual_memory()
    return round(vm.total / (1024**3), 2), round(vm.available / (1024**3), 2)


def _run(cmd: list[str], timeout: float = SUBPROCESS_TIMEOUT_SECONDS) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


def _detect_nvidia_gpus() -> list[GPUInfo]:
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return []

    gpus: list[GPUInfo] = []
    for line in output.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        name, total_mb, free_mb, compute_cap = parts
        try:
            gpus.append(
                GPUInfo(
                    name=name,
                    vram_total_mb=int(float(total_mb)),
                    vram_available_mb=int(float(free_mb)),
                    driver="nvidia",
                    compute_capability=compute_cap,
                )
            )
        except ValueError:
            continue
    return gpus


def _detect_amd_gpus() -> list[GPUInfo]:
    output = _run(["rocm-smi", "--showmeminfo", "vram", "--json"])
    if not output:
        return []
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    gpus: list[GPUInfo] = []
    for card in data.values():
        if not isinstance(card, dict):
            continue
        total = card.get("VRAM Total Memory (B)")
        used = card.get("VRAM Total Used Memory (B)")
        if total is None:
            continue
        total_mb = int(int(total) / (1024**2))
        free_mb = total_mb - int(int(used or 0) / (1024**2))
        gpus.append(
            GPUInfo(
                name="AMD GPU",
                vram_total_mb=total_mb,
                vram_available_mb=max(free_mb, 0),
                driver="amd",
            )
        )
    return gpus


def _detect_apple_gpu(os_name: str) -> list[GPUInfo]:
    if os_name != "macos":
        return []
    output = _run(["system_profiler", "SPDisplaysDataType", "-json"])
    if not output:
        return []
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    gpus: list[GPUInfo] = []
    for entry in data.get("SPDisplaysDataType", []):
        name = entry.get("sppci_model", "Apple GPU")
        # Apple Silicon shares system RAM with the GPU; there's no separate
        # VRAM figure to query, so we report system RAM as an upper bound.
        _, ram_available_gb = _detect_ram()
        gpus.append(
            GPUInfo(
                name=name,
                vram_total_mb=int(ram_available_gb * 1024),
                vram_available_mb=int(ram_available_gb * 1024),
                driver="apple",
            )
        )
    return gpus


def _detect_gpus(os_name: str) -> list[GPUInfo]:
    gpus = _detect_nvidia_gpus()
    if gpus:
        return gpus
    gpus = _detect_amd_gpus()
    if gpus:
        return gpus
    gpus = _detect_apple_gpu(os_name)
    if gpus:
        return gpus
    return []


def _detect_docker() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=DOCKER_TIMEOUT_SECONDS,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _detect_ollama() -> tuple[bool, list[str]]:
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return False, []
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return True, models
    except Exception:  # noqa: BLE001 — any failure here just means "not detected"
        return False, []


def detect_hardware() -> HardwareProfile:
    """Run every probe and assemble a full HardwareProfile.

    Safe to call repeatedly (e.g. from a "re-run detection" button) — each
    probe re-checks live state rather than caching.
    """
    os_name = _detect_os()
    cpu_cores, cpu_name = _detect_cpu()
    ram_total_gb, ram_available_gb = _detect_ram()
    gpus = _detect_gpus(os_name)
    docker_available = _detect_docker()
    ollama_available, ollama_models = _detect_ollama()

    return HardwareProfile(
        os=os_name,
        cpu_cores=cpu_cores,
        cpu_name=cpu_name,
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_available_gb,
        gpus=gpus,
        docker_available=docker_available,
        ollama_available=ollama_available,
        ollama_models=ollama_models,
    )
