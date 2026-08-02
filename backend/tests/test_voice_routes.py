"""HTTP + WebSocket tests for /voice/* — real WebSocket handshakes and
binary frames via Starlette's TestClient (no browser involved, but a real
protocol exchange, not a mock)."""

from __future__ import annotations

import struct


def test_list_voices_returns_voices_list(client):
    resp = client.get("/voice/tts/voices")
    assert resp.status_code == 200
    voices = resp.json()
    assert len(voices) >= 1
    assert "id" in voices[0]


def test_synthesize_streaming_returns_valid_wav_audio(client):
    resp = client.post("/voice/tts/synthesize", json={"text": "Hello world", "stream": True})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert resp.content[:4] == b"RIFF"


def test_synthesize_non_streaming_also_returns_valid_wav(client):
    resp = client.post("/voice/tts/synthesize", json={"text": "Hello world", "stream": False})
    assert resp.status_code == 200
    assert resp.content[:4] == b"RIFF"


def test_list_devices_returns_a_list_without_crashing(client):
    resp = client.get("/voice/devices")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def _tone_pcm16_bytes(n_samples: int = 480, freq: float = 200.0, amplitude: float = 0.3) -> bytes:
    import math

    values = [
        int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / 16000)) for i in range(n_samples)
    ]
    return struct.pack(f"<{n_samples}h", *values)


def _silence_pcm16_bytes(n_samples: int = 480) -> bytes:
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def test_vad_status_websocket_classifies_tone_as_speech(client):
    with client.websocket_connect("/voice/vad/status") as ws:
        ws.send_bytes(_tone_pcm16_bytes())
        response = ws.receive_json()

    assert response["is_speech"] is True
    assert response["timestamp_ms"] == 0


def test_vad_status_websocket_classifies_silence_as_not_speech(client):
    with client.websocket_connect("/voice/vad/status") as ws:
        ws.send_bytes(_silence_pcm16_bytes())
        response = ws.receive_json()

    assert response["is_speech"] is False


def test_vad_status_websocket_increments_timestamp_across_frames(client):
    with client.websocket_connect("/voice/vad/status") as ws:
        ws.send_bytes(_silence_pcm16_bytes())
        first = ws.receive_json()
        ws.send_bytes(_silence_pcm16_bytes())
        second = ws.receive_json()

    assert first["timestamp_ms"] == 0
    assert second["timestamp_ms"] == 30


def test_stt_stream_websocket_reports_model_unavailable_gracefully(client):
    # faster-whisper isn't installed in this environment, so this exercises
    # the real graceful-degradation path end to end over an actual socket.
    with client.websocket_connect("/voice/stt/stream") as ws:
        ws.send_bytes(_tone_pcm16_bytes())
        response = ws.receive_json()

    assert "error" in response
    assert "model_name" in response
    assert response["model_name"] == "tiny"  # default CLOUD_ASSIST tier
