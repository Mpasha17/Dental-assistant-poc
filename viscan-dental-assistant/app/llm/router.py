"""Choose an interpreter and fall back to the rule parser when it cannot run."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from app.config import Settings, get_settings
from app.llm.base import ToolCall
from app.llm.rule_based import RuleBasedProvider
from app.logging_utils import get_logger

logger = get_logger()
_router: "ProviderRouter | None" = None


def _fallback_reason(exc: Exception) -> str:
    """A short label for the log. The raw SDK text can echo the prompt."""

    text = str(exc)
    if "client has been closed" in text:
        return "client_closed"
    if "no longer available" in text or "NOT_FOUND" in text or "not found" in text:
        return "model_not_found"
    if "quota" in text.lower() or "RESOURCE_EXHAUSTED" in text or "429" in text:
        return "rate_limited"
    if "UNAVAILABLE" in text or "high demand" in text or "DEADLINE_EXCEEDED" in text:
        return "unavailable"
    return type(exc).__name__


def call_with_timeout(func: Any, timeout_s: float) -> Any:
    """Run a provider call until LLM_TIMEOUT_S. The worker is not cancelled."""

    if timeout_s <= 0:
        return func()
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func)
    try:
        return future.result(timeout=timeout_s)
    except FuturesTimeout as exc:
        raise TimeoutError(f"LLM timed out after {timeout_s}s") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class ProviderRouter:
    """Try the configured provider, then the deterministic parser."""

    def __init__(self, primary: Any, fallback: RuleBasedProvider, timeout_s: float) -> None:
        self.primary = primary
        self.fallback = fallback
        self.timeout_s = timeout_s
        self.used_fallback = False

    def _attempt(self, operation: str, func: Any) -> Any:
        """Call the provider. A single 'unavailable' response is retried once."""

        try:
            return call_with_timeout(func, self.timeout_s)
        except Exception as first:
            if _fallback_reason(first) != "unavailable":
                raise
            logger.warning("llm_retry op=%s reason=unavailable", operation)
            return call_with_timeout(func, self.timeout_s)

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> tuple[ToolCall, str]:
        self.used_fallback = False
        if getattr(self.primary, "name", "") == "rule":
            return self.primary.interpret(text, context, tools), "rule"
        try:
            result = self._attempt("interpret", lambda: self.primary.interpret(text, context, tools))
            return result, str(self.primary.name)
        except Exception as exc:
            self.used_fallback = True
            logger.warning("llm_fallback op=interpret reason=%s", _fallback_reason(exc))
            return self.fallback.interpret(text, context, tools), "rule"

    def generate(self, prompt: str, json_schema: dict[str, Any]) -> tuple[dict[str, Any], str]:
        self.used_fallback = False
        if getattr(self.primary, "name", "") == "rule":
            return self.primary.generate(prompt, json_schema), "rule"
        try:
            result = self._attempt("generate", lambda: self.primary.generate(prompt, json_schema))
            if not isinstance(result, dict):
                raise TypeError("provider returned non-object JSON")
            return result, str(self.primary.name)
        except Exception as exc:
            self.used_fallback = True
            logger.warning("llm_fallback op=generate reason=%s", _fallback_reason(exc))
            return self.fallback.generate(prompt, json_schema), "rule"


def build_router(settings: Settings | None = None) -> ProviderRouter:
    """Build the router. A missing key selects the rule parser immediately."""

    settings = settings or get_settings()
    fallback = RuleBasedProvider()
    provider = settings.llm_provider
    primary: Any = fallback
    if provider == "gemini" and settings.gemini_api_key:
        from app.llm.gemini import GeminiProvider

        primary = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    elif provider == "mistral" and settings.mistral_api_key:
        from app.llm.mistral import MistralProvider

        primary = MistralProvider(settings.mistral_api_key, settings.mistral_model)
    elif provider == "groq" and settings.groq_api_key:
        from app.llm.groq_llm import GroqProvider

        primary = GroqProvider(settings.groq_api_key, settings.groq_model)
    elif provider not in {"rule", "gemini", "mistral", "groq"}:
        logger.warning("unknown_llm_provider provider=%s", provider)
    elif provider != "rule":
        logger.info("llm_key_missing provider=%s fallback=rule", provider)
    return ProviderRouter(primary, fallback, settings.llm_timeout_s)


def get_llm_router() -> ProviderRouter:
    global _router
    if _router is None:
        _router = build_router()
    return _router


def reset_llm_router() -> None:
    global _router
    _router = None
