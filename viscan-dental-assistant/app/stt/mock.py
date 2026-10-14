"""Speech adapter for tests: a form field, or a .txt file beside the audio."""

from __future__ import annotations

from pathlib import Path

from app.stt.base import Transcript


class MockSTT:
    name = "mock"

    def transcribe(
        self,
        audio_bytes: bytes,
        mime: str,
        filename: str | None = None,
        transcript_hint: str | None = None,
    ) -> Transcript:
        if transcript_hint and transcript_hint.strip():
            return Transcript(text=transcript_hint.strip(), confidence=1.0, provider=self.name)
        if filename:
            sidecar = Path(filename).with_suffix(".txt")
            if sidecar.is_file():
                return Transcript(text=sidecar.read_text(encoding="utf-8").strip(), confidence=1.0, provider=self.name)
        raise ValueError("Mock speech-to-text needs a transcript field or a sidecar .txt file.")
