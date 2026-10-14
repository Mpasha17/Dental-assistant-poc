"""Transcript type shared by every speech adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Transcript:
    text: str
    confidence: float | None
    provider: str


class STTProvider(Protocol):
    name: str

    def transcribe(
        self,
        audio_bytes: bytes,
        mime: str,
        filename: str | None = None,
        transcript_hint: str | None = None,
    ) -> Transcript:
        """Turn audio bytes into text."""
