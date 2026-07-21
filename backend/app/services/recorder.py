"""Session audio recording.

Saves WAV files under `{data_dir}/sessions/{session_id}/audio/`, plus a
`metadata.json` alongside recording which speaker said what and when — the
exact shape the Phase 3 spec's §3.8 calls for and what Phase 8 (Scoring &
Progress) needs for session replay with a timeline overlay.

Pure file I/O — no audio hardware, no ML model, nothing that can't run
and be fully tested in any environment.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Speaker = Literal["user", "ai"]


@dataclass
class AudioClipMetadata:
    filename: str
    speaker: Speaker
    start_ms: int
    end_ms: int
    vad_boundaries: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class SessionAudioManifest:
    session_id: str
    clips: list[AudioClipMetadata] = field(default_factory=list)


class SessionAudioRecorder:
    def __init__(self, data_dir: Path, session_id: str) -> None:
        self.session_id = session_id
        self.session_dir = data_dir / "sessions" / session_id
        self.audio_dir = self.session_dir / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._manifest = self._load_manifest()

    @property
    def manifest_path(self) -> Path:
        return self.session_dir / "metadata.json"

    def _load_manifest(self) -> SessionAudioManifest:
        if self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text())
            clips = [
                AudioClipMetadata(
                    filename=c["filename"],
                    speaker=c["speaker"],
                    start_ms=c["start_ms"],
                    end_ms=c["end_ms"],
                    vad_boundaries=[tuple(b) for b in c.get("vad_boundaries", [])],
                )
                for c in data.get("clips", [])
            ]
            return SessionAudioManifest(session_id=self.session_id, clips=clips)
        return SessionAudioManifest(session_id=self.session_id)

    def save_clip(
        self,
        wav_bytes: bytes,
        speaker: Speaker,
        start_ms: int,
        end_ms: int,
        vad_boundaries: list[tuple[int, int]] | None = None,
    ) -> AudioClipMetadata:
        """Writes one WAV clip to disk and records it in the manifest.
        Filenames are zero-padded by start_ms so a directory listing sorts
        into playback order without needing to parse the manifest first."""
        filename = f"{start_ms:010d}_{speaker}.wav"
        (self.audio_dir / filename).write_bytes(wav_bytes)

        clip = AudioClipMetadata(
            filename=filename,
            speaker=speaker,
            start_ms=start_ms,
            end_ms=end_ms,
            vad_boundaries=vad_boundaries or [],
        )
        self._manifest.clips.append(clip)
        self._manifest.clips.sort(key=lambda c: c.start_ms)
        self._write_manifest()
        return clip

    def _write_manifest(self) -> None:
        payload = {
            "session_id": self._manifest.session_id,
            "clips": [asdict(c) for c in self._manifest.clips],
        }
        self.manifest_path.write_text(json.dumps(payload, indent=2))

    def load_manifest(self) -> SessionAudioManifest:
        return self._load_manifest()

    def clip_path(self, filename: str) -> Path:
        return self.audio_dir / filename
