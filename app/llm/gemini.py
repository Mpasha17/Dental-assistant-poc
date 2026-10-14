"""Gemini interpreter. The google-genai import stays inside the methods."""

from __future__ import annotations

import json
from typing import Any

from app.llm.base import ToolCall, coerce_args, interpreter_messages


def _function_declaration(types: Any, tool: dict[str, Any]) -> Any:
    description = tool["description"]
    name = tool["name"]
    parameters = tool["parameters"]
    try:
        return types.FunctionDeclaration(
            name=name,
            description=description,
            parameters_json_schema=parameters,
        )
    except Exception:
        return types.FunctionDeclaration(
            name=name,
            description=description,
            parameters=_as_schema(types, parameters),
        )


def _as_schema(types: Any, node: dict[str, Any]) -> Any:
    type_name = node.get("type", "string")
    if isinstance(type_name, list):
        type_name = next((item for item in type_name if item != "null"), "string")
    schema_type = getattr(types.Type, str(type_name).upper(), types.Type.OBJECT)
    kwargs: dict[str, Any] = {"type": schema_type}
    if node.get("description"):
        kwargs["description"] = node["description"]
    if node.get("enum"):
        kwargs["enum"] = [str(item) for item in node["enum"]]
    if type_name == "object":
        kwargs["properties"] = {
            key: _as_schema(types, value) for key, value in (node.get("properties") or {}).items()
        }
        if node.get("required"):
            kwargs["required"] = list(node["required"])
    if type_name == "array" and isinstance(node.get("items"), dict):
        kwargs["items"] = _as_schema(types, node["items"])
    return types.Schema(**kwargs)


class GeminiProvider:
    """Native function calling on Gemini, with JSON mode for dictation."""

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def _client(self) -> Any:
        """Keep one client. A temporary client is closed by its destructor mid-request."""

        client = getattr(self, "_genai", None)
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=20_000),
            )
            self._genai = client
        return client

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> ToolCall:
        from google.genai import types

        system, user = interpreter_messages(text, context)
        declarations = [_function_declaration(types, tool) for tool in tools]
        client = self._client()
        response = client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                tools=[types.Tool(function_declarations=declarations)],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        calls = getattr(response, "function_calls", None) or []
        if not calls:
            return ToolCall("unknown", {"utterance": text})
        call = calls[0]
        return ToolCall(str(call.name), coerce_args(call.args))

    def generate(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        from google.genai import types

        config_kwargs: dict[str, Any] = {"temperature": 0, "response_mime_type": "application/json"}
        try:
            config = types.GenerateContentConfig(**config_kwargs, response_json_schema=json_schema)
        except Exception:
            config = types.GenerateContentConfig(**config_kwargs, response_schema=json_schema)
        client = self._client()
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return json.loads(response.text or "{}")
