"""Environment settings. Secrets stay in the environment and are never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
ENV_PATH = ROOT / ".env"


def load_dotenv_file(path: Path = ENV_PATH) -> None:
    """Fill missing environment variables from a local .env file.

    Existing variables win, so tests and the shell can override the file.
    """

    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded once per process, unless tests reset it."""

    llm_provider: str
    gemini_api_key: str
    gemini_model: str
    mistral_api_key: str
    mistral_model: str
    groq_api_key: str
    groq_model: str
    groq_whisper_model: str
    stt_provider: str
    local_whisper_model: str
    llm_timeout_s: float
    log_level: str
    demo_date: date
    max_text_chars: int = 2000
    max_audio_bytes: int = 10 * 1024 * 1024

    def key_present(self, provider: str) -> bool:
        return {
            "gemini": bool(self.gemini_api_key),
            "mistral": bool(self.mistral_api_key),
            "groq": bool(self.groq_api_key),
        }.get(provider, False)


def load_settings() -> Settings:
    """Read settings from the environment, after applying .env defaults."""

    load_dotenv_file()
    try:
        timeout = float(_env("LLM_TIMEOUT_S", "15"))
    except ValueError:
        timeout = 15.0
    try:
        demo = date.fromisoformat(_env("DEMO_DATE", "2026-10-14"))
    except ValueError:
        demo = date(2026, 10, 14)
    return Settings(
        llm_provider=_env("LLM_PROVIDER", "gemini").lower(),
        gemini_api_key=_env("GEMINI_API_KEY", ""),
        gemini_model=_env("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        mistral_api_key=_env("MISTRAL_API_KEY", ""),
        mistral_model=_env("MISTRAL_MODEL", "mistral-small-latest"),
        groq_api_key=_env("GROQ_API_KEY", ""),
        groq_model=_env("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_whisper_model=_env("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        stt_provider=_env("STT_PROVIDER", "groq").lower(),
        local_whisper_model=_env("LOCAL_WHISPER_MODEL", "base.en"),
        llm_timeout_s=timeout,
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        demo_date=demo,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings() -> Settings:
    """Drop the cached settings. Used by tests that change the environment."""

    get_settings.cache_clear()
    return get_settings()
