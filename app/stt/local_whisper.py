"""Local faster-whisper. The package is optional and imported lazily."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.config import get_settings
from app.stt.base import Transcript
from app.tools.store import vocab

_model: object | None = None


def _get_model() -> object:
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        _model = WhisperModel(settings.local_whisper_model, device="cpu", compute_type="int8")
    return _model


class LocalWhisperSTT:
    name = "local"

    def transcribe(
        self,
        audio_bytes: bytes,
        mime: str,
        filename: str | None = None,
        transcript_hint: str | None = None,
    ) -> Transcript:
        suffix = Path(filename).suffix if filename else ".webm"
        if suffix.lower() not in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}:
            suffix = ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as handle:
            handle.write(audio_bytes)
            handle.flush()
            segments, info = _get_model().transcribe(  # type: ignore[attr-defined]
                handle.name,
                language="en",
                initial_prompt=str(vocab().get("prompt") or ""),
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        confidence = getattr(info, "language_probability", None)
        return Transcript(text=text, confidence=confidence, provider=self.name)
