"""Tool declarations shared by every model provider, plus the Python executors."""

from __future__ import annotations

from typing import Any

from app.tools.booking import book_slot, check_slots
from app.tools.patients import resolve_patient, public_patient
from app.tools.reports import answer_report_question, get_report, list_reports, report_summary, summarize_report

_OBJECT = "object"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "find_patient",
        "description": "Resolve a spoken or typed patient name. Do not invent an id.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "name": {"type": "string", "description": "Patient name as spoken or typed."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_reports",
        "description": "List a patient's reports. Pass the spoken name; the server resolves the id.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "patient_id": {"type": "string", "description": "Known id such as P003. Leave empty if unsure."},
                "name": {"type": "string", "description": "Spoken patient name."},
                "report_type": {"type": "string", "description": "Optional OPG, IOPA, CBCT, or Bitewing."},
            },
        },
    },
    {
        "name": "get_report",
        "description": "Fetch one report. Use which=latest unless the user asks for the oldest.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "patient_id": {"type": "string"},
                "name": {"type": "string", "description": "Spoken patient name, resolved by the server."},
                "report_type": {"type": "string"},
                "which": {"type": "string", "enum": ["latest", "oldest"]},
            },
        },
    },
    {
        "name": "summarize_report",
        "description": "Summarize the report already open in the session.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "report_id": {"type": "string"},
                "pronoun": {"type": "string", "description": "her, his, or their when the user used one."},
            },
        },
    },
    {
        "name": "answer_report_question",
        "description": "Answer a question using only the selected report.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "report_id": {"type": "string"},
                "question": {"type": "string"},
                "pronoun": {"type": "string"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "draft_clinical_report",
        "description": "Extract findings from a clinical dictation transcript. Copy the transcript verbatim.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "transcript": {"type": "string"},
                "patient_id": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["transcript"],
        },
    },
    {
        "name": "check_slots",
        "description": "Find scan slots. This does not book. Pass the spoken patient name in name.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "scan_type": {"type": "string"},
                "date_from": {"type": "string", "description": "ISO date."},
                "date_to": {"type": "string", "description": "ISO date."},
                "part_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening"]},
                "name": {"type": "string"},
                "patient_id": {"type": "string"},
                "slot_id": {"type": "string"},
            },
        },
    },
    {
        "name": "book_slot",
        "description": "Book a slot only when the user has explicitly confirmed it.",
        "parameters": {
            "type": _OBJECT,
            "properties": {
                "slot_id": {"type": "string"},
                "patient_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["slot_id", "patient_id", "confirmed"],
        },
    },
]

ALLOWED_TOOLS = {tool["name"] for tool in TOOL_SCHEMAS}


def tool_schemas() -> list[dict[str, Any]]:
    return TOOL_SCHEMAS


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run a validated tool. Draft reports are assembled by the orchestrator."""

    if name == "find_patient":
        result = resolve_patient(str(arguments.get("name") or ""))
        return {
            "status": result.status,
            "patients": [public_patient(patient) for patient in result.patients],
        }
    if name == "list_reports":
        rows = list_reports(str(arguments["patient_id"]), arguments.get("report_type"))
        return {"reports": [report_summary(row) | {"impression": row["impression"]} for row in rows]}
    if name == "get_report":
        return get_report(
            str(arguments["patient_id"]),
            arguments.get("report_type"),
            str(arguments.get("which") or "latest"),
        )
    if name == "summarize_report":
        return summarize_report(str(arguments["report_id"]))
    if name == "answer_report_question":
        return answer_report_question(str(arguments["report_id"]), str(arguments["question"]))
    if name == "check_slots":
        return {
            "slots": check_slots(
                arguments.get("scan_type"),
                arguments.get("date_from"),
                arguments.get("date_to"),
                arguments.get("part_of_day"),
            )
        }
    if name == "book_slot":
        return book_slot(
            str(arguments["slot_id"]),
            str(arguments["patient_id"]),
            bool(arguments.get("confirmed")),
        )
    raise KeyError(name)
