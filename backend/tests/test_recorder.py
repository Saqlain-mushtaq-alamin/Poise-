"""SessionAudioRecorder — real file I/O against a tmp_path, no mocking
needed since this is pure filesystem logic."""

from __future__ import annotations

import json

from app.services.audio_utils import generate_tone_samples, pcm16_to_wav_bytes
from app.services.recorder import SessionAudioRecorder


def _fake_wav() -> bytes:
    return pcm16_to_wav_bytes(generate_tone_samples(duration_seconds=0.1))


def test_creates_session_audio_directory(tmp_path):
    recorder = SessionAudioRecorder(tmp_path, "session-1")
    assert recorder.audio_dir.exists()
    assert recorder.audio_dir == tmp_path / "sessions" / "session-1" / "audio"


def test_save_clip_writes_wav_file_to_disk(tmp_path):
    recorder = SessionAudioRecorder(tmp_path, "session-1")
    clip = recorder.save_clip(_fake_wav(), speaker="user", start_ms=0, end_ms=1000)

    saved_path = recorder.clip_path(clip.filename)
    assert saved_path.exists()
    assert saved_path.read_bytes()[:4] == b"RIFF"


def test_save_clip_records_manifest_entry(tmp_path):
    recorder = SessionAudioRecorder(tmp_path, "session-1")
    recorder.save_clip(_fake_wav(), speaker="user", start_ms=0, end_ms=1000)
    recorder.save_clip(_fake_wav(), speaker="ai", start_ms=1000, end_ms=2500)

    manifest = recorder.load_manifest()
    assert len(manifest.clips) == 2
    assert manifest.clips[0].speaker == "user"
    assert manifest.clips[1].speaker == "ai"


def test_clips_sorted_by_start_time_regardless_of_save_order(tmp_path):
    recorder = SessionAudioRecorder(tmp_path, "session-1")
    recorder.save_clip(_fake_wav(), speaker="ai", start_ms=5000, end_ms=6000)
    recorder.save_clip(_fake_wav(), speaker="user", start_ms=0, end_ms=1000)

    manifest = recorder.load_manifest()
    assert [c.start_ms for c in manifest.clips] == [0, 5000]


def test_manifest_persists_across_recorder_instances(tmp_path):
    recorder1 = SessionAudioRecorder(tmp_path, "session-1")
    recorder1.save_clip(_fake_wav(), speaker="user", start_ms=0, end_ms=1000)

    recorder2 = SessionAudioRecorder(tmp_path, "session-1")
    manifest = recorder2.load_manifest()
    assert len(manifest.clips) == 1


def test_manifest_json_is_well_formed_on_disk(tmp_path):
    recorder = SessionAudioRecorder(tmp_path, "session-1")
    recorder.save_clip(
        _fake_wav(), speaker="user", start_ms=0, end_ms=1000, vad_boundaries=[(100, 900)]
    )

    data = json.loads(recorder.manifest_path.read_text())
    assert data["session_id"] == "session-1"
    assert data["clips"][0]["vad_boundaries"] == [[100, 900]]


def test_different_sessions_are_isolated(tmp_path):
    recorder_a = SessionAudioRecorder(tmp_path, "session-a")
    recorder_b = SessionAudioRecorder(tmp_path, "session-b")
    recorder_a.save_clip(_fake_wav(), speaker="user", start_ms=0, end_ms=1000)

    assert len(recorder_a.load_manifest().clips) == 1
    assert len(recorder_b.load_manifest().clips) == 0


def test_filename_is_zero_padded_for_sort_order(tmp_path):
    recorder = SessionAudioRecorder(tmp_path, "session-1")
    clip = recorder.save_clip(_fake_wav(), speaker="user", start_ms=42, end_ms=100)
    assert clip.filename.startswith("0000000042_")
