"""Groq Whisper. The groq SDK is imported only when a clip is transcribed."""

from __future__ import annotations

import io

from app.config import get_settings
from app.stt.base import Transcript
from app.tools.store import vocab


def _filename(mime: str, filename: str | None) -> str:
    if filename:
        return filename
    mapping = {
        "audio/webm": "audio.webm",
        "video/webm": "audio.webm",
        "audio/wav": "audio.wav",
        "audio/x-wav": "audio.wav",
        "audio/mpeg": "audio.mp3",
        "audio/mp3": "audio.mp3",
        "audio/mp4": "audio.m4a",
        "audio/m4a": "audio.m4a",
        "audio/x-m4a": "audio.m4a",
        "audio/ogg": "audio.ogg",
    }
    return mapping.get(mime.split(";")[0].strip().lower(), "audio.webm")


class GroqWhisperSTT:
    name = "groq"

    def transcribe(
        self,
        audio_bytes: bytes,
        mime: str,
        filename: str | None = None,
        transcript_hint: str | None = None,
    ) -> Transcript:
        settings = get_settings()
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        from groq import Groq

        buffer = io.BytesIO(audio_bytes)
        buffer.name = _filename(mime, filename)
        result = Groq(api_key=settings.groq_api_key).audio.transcriptions.create(
            file=buffer,
            model=settings.groq_whisper_model,
            prompt=str(vocab().get("prompt") or ""),
            response_format="json",
            language="en",
        )
        text = getattr(result, "text", None) or str(result)
        return Transcript(text=text.strip(), confidence=None, provider=self.name)
