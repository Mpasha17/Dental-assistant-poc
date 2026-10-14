"""Shared interpreter types. Provider SDKs are imported only inside their modules."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """A proposed tool call. Validation still has to accept it."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    """interpret() chooses a tool. generate() returns JSON for dictation."""

    name: str

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> ToolCall:
        """Map one utterance to a single tool call."""

    def generate(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object that follows json_schema."""


_SYSTEM_PROMPT = (
    "You are the intent interpreter for Viscan, a dental radiology assistant. "
    "Choose exactly one tool. Do not answer clinical questions yourself and do not "
    "invent patient ids, report contents, tooth numbers, or bookings. "
    "Pass the spoken patient name in the name argument. Greetings and small talk such as "
    "'hi', 'hello', or 'thanks' are never patient names. Leave patient_id empty unless "
    "the conversation context already contains that id. "
    "Use the current report for follow-ups such as 'her report' only when context has a report_id. "
    "When context has a report_id and the user asks to summarize 'her report', 'his report', "
    "'their report', or 'the report' without naming another patient, call summarize_report with "
    "that report_id. Never call list_reports for a summary request. Call list_reports only when "
    "the user asks which reports exist. "
    "For a booking request call check_slots. Call book_slot with confirmed=true only when "
    "the user explicitly confirms a pending slot. "
    "For clinical dictation call draft_clinical_report and copy the transcript verbatim."
)


def interpreter_messages(text: str, context: dict[str, Any]) -> tuple[str, str]:
    """System and user messages shared by the hosted interpreters."""

    user = "Context JSON:\n" + json.dumps(context, default=str) + "\n\nUser message:\n" + text
    return _SYSTEM_PROMPT, user


def coerce_args(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "items"):
        return {str(key): item for key, item in value.items()}
    return {}
