"""Tests for hardware detection. All subprocess/network calls are mocked —
this suite never assumes nvidia-smi, Docker, or Ollama are actually
installed on the machine running the tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import hardware


def test_detect_hardware_degrades_gracefully_with_nothing_installed():
    with (
        patch("app.services.hardware.shutil.which", return_value=None),
        patch("app.services.hardware.httpx.get", side_effect=OSError("no network")),
    ):
        profile = hardware.detect_hardware()

    assert profile.gpus == []
    assert profile.docker_available is False
    assert profile.ollama_available is False
    assert profile.ram_total_gb > 0
    assert profile.cpu_cores >= 1
    assert profile.os in {"windows", "macos", "linux"}


def test_detect_nvidia_gpus_parses_csv_output():
    csv_output = "NVIDIA GeForce RTX 4060, 8188, 7200, 8.9\n"
    with (
        patch("app.services.hardware.shutil.which", return_value="/usr/bin/nvidia-smi"),
        patch("app.services.hardware.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=csv_output)
        gpus = hardware._detect_nvidia_gpus()

    assert len(gpus) == 1
    gpu = gpus[0]
    assert gpu.name == "NVIDIA GeForce RTX 4060"
    assert gpu.vram_total_mb == 8188
    assert gpu.vram_available_mb == 7200
    assert gpu.driver == "nvidia"
    assert gpu.compute_capability == "8.9"


def test_detect_nvidia_gpus_returns_empty_when_tool_missing():
    with patch("app.services.hardware.shutil.which", return_value=None):
        assert hardware._detect_nvidia_gpus() == []


def test_detect_nvidia_gpus_handles_malformed_lines():
    with (
        patch("app.services.hardware.shutil.which", return_value="/usr/bin/nvidia-smi"),
        patch("app.services.hardware.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="garbage, not, csv\n")
        assert hardware._detect_nvidia_gpus() == []


def test_detect_docker_false_when_daemon_not_running():
    with (
        patch("app.services.hardware.shutil.which", return_value="/usr/bin/docker"),
        patch("app.services.hardware.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1)
        assert hardware._detect_docker() is False


def test_detect_docker_true_when_daemon_running():
    with (
        patch("app.services.hardware.shutil.which", return_value="/usr/bin/docker"),
        patch("app.services.hardware.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        assert hardware._detect_docker() is True


def test_detect_ollama_reports_models_when_reachable():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3"}]}

    with patch("app.services.hardware.httpx.get", return_value=fake_response):
        reachable, models = hardware._detect_ollama()

    assert reachable is True
    assert models == ["qwen2.5:7b", "llama3"]


def test_detect_ollama_false_when_unreachable():
    with patch("app.services.hardware.httpx.get", side_effect=OSError("connection refused")):
        reachable, models = hardware._detect_ollama()

    assert reachable is False
    assert models == []
