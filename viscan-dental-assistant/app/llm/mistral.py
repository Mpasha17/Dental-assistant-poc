"""Mistral interpreter. The mistralai import stays inside the methods."""

from __future__ import annotations

import json
from typing import Any

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


class MistralProvider:
    """Tool calling on the Mistral chat API."""

    name = "mistral"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> ToolCall:
        system, user = interpreter_messages(text, context)
        response = _client(self.api_key).chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=_openai_tools(tools),
            tool_choice="any",
            temperature=0,
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
        response = _client(self.api_key).chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        if isinstance(content, list):
            content = "".join(str(getattr(part, "text", part)) for part in content)
        return json.loads(content)
