"""Select the speech adapter named by STT_PROVIDER."""

from __future__ import annotations

from app.config import get_settings
from app.logging_utils import get_logger
from app.stt.base import STTProvider
from app.stt.mock import MockSTT

logger = get_logger()


def build_stt() -> STTProvider:
    provider = get_settings().stt_provider
    if provider == "mock":
        return MockSTT()
    if provider == "local":
        from app.stt.local_whisper import LocalWhisperSTT

        return LocalWhisperSTT()
    if provider == "groq":
        from app.stt.groq_whisper import GroqWhisperSTT

        if not get_settings().groq_api_key:
            logger.info("stt_key_missing provider=groq")
        return GroqWhisperSTT()
    logger.warning("unknown_stt_provider provider=%s fallback=mock", provider)
    return MockSTT()


def get_stt() -> STTProvider:
    return build_stt()
