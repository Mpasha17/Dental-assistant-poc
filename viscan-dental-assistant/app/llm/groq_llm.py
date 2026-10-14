"""Groq chat interpreter. The groq import stays inside the methods."""

from __future__ import annotations

import json
from typing import Any

from app.llm.base import ToolCall, coerce_args, interpreter_messages
from app.llm.mistral import _openai_tools


class GroqProvider:
    """Tool calling against Groq's OpenAI-compatible chat API."""

    name = "groq"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def _client(self) -> Any:
        from groq import Groq

        return Groq(api_key=self.api_key)

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> ToolCall:
        system, user = interpreter_messages(text, context)
        response = self._client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=_openai_tools(tools),
            tool_choice="required",
            temperature=0,
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        if not tool_calls:
            return ToolCall("unknown", {"utterance": text})
        call = tool_calls[0]
        return ToolCall(call.function.name, coerce_args(call.function.arguments))

    def generate(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        response = self._client().chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content or "{}")
