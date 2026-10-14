"""Mistral interpreter. The mistralai import stays inside the methods."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from app.llm.base import ToolCall, coerce_args, interpreter_messages


def _openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in tools
    ]


def _client(api_key: str) -> Any:
    try:
        from mistralai import Mistral
    except ImportError:
        from mistralai.client import Mistral  # type: ignore
    return Mistral(api_key=api_key)


RETRY_BASE_DELAY_S = 1.5
MAX_RATE_LIMIT_RETRIES = 2


def _is_rate_limited(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "raw_response", None), "status_code", None)
    if status == 429:
        return True
    text = str(exc)
    return "429" in text or "rate limit" in text.lower()


def with_rate_limit_retry(func: Callable[[], Any], sleep: Callable[[float], None] = time.sleep) -> Any:
    """Retry a 429 with exponential backoff (1.5s, then 3s). After that the error propagates
    so the router can fall back to the rule parser."""

    attempt = 0
    while True:
        try:
            return func()
        except Exception as exc:
            if not _is_rate_limited(exc) or attempt >= MAX_RATE_LIMIT_RETRIES:
                raise
            sleep(RETRY_BASE_DELAY_S * (2**attempt))
            attempt += 1


class MistralProvider:
    """Tool calling on the Mistral chat API."""

    name = "mistral"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> ToolCall:
        system, user = interpreter_messages(text, context)
        client = _client(self.api_key)
        response = with_rate_limit_retry(
            lambda: client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=_openai_tools(tools),
                tool_choice="any",
                temperature=0,
            )
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            return ToolCall("unknown", {"utterance": text})
        call = tool_calls[0]
        function = getattr(call, "function", call)
        name = getattr(function, "name", None) or call.get("function", {}).get("name")
        arguments = getattr(function, "arguments", None)
        if arguments is None and isinstance(call, dict):
            arguments = call.get("function", {}).get("arguments")
        return ToolCall(str(name), coerce_args(arguments))

    def generate(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        client = _client(self.api_key)
        response = with_rate_limit_retry(
            lambda: client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
        )
        content = response.choices[0].message.content or "{}"
        if isinstance(content, list):
            content = "".join(str(getattr(part, "text", part)) for part in content)
        return json.loads(content)
