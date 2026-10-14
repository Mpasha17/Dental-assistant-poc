"""Validate a proposed tool call before any tool is allowed to run."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.llm.base import ToolCall
from app.llm.rule_based import (
    GREETING_REPLY,
    extract_name,
    is_greeting,
    is_confirmation,
    looks_like_new_request,
    parse_booking,
    pronoun_of,
    which_report,
)
from app.validation.report_types import detect_report_type
from app.schemas import TOOL_ARG_MODELS
from app.session import Session
from app.tools.patients import (
    all_options,
    clarification_option,
    get_patient,
    resolve_patient,
    select_candidate,
)
from app.tools.registry import ALLOWED_TOOLS
from app.tools.reports import list_reports
from app.validation.report_types import canonical_report_type

_PATIENT_TOOLS = {"find_patient", "list_reports", "get_report", "check_slots", "draft_clinical_report"}
_REPORT_TOOLS = {"summarize_report", "answer_report_question"}


@dataclass
class Outcome:
    """Either a tool call that is safe to execute, or a finished clarification."""

    handled: bool = False
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    patient: dict[str, Any] | None = None
    intent: str = "unknown"
    answer: str = ""
    data: Any = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_options: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_clinician_review: bool = False


def _finish_clarification(
    session: Session,
    tool: str,
    args: dict[str, Any],
    candidates: list[dict[str, Any]],
    answer: str,
    warnings: list[str] | None = None,
) -> Outcome:
    ordered = sorted(candidates, key=lambda patient: patient["id"])
    session.pending_clarification = {"tool": tool, "args": args, "candidates": ordered}
    session.pending_booking = None
    return Outcome(
        handled=True,
        intent="clarify_patient",
        answer=answer,
        data=None,
        needs_clarification=True,
        clarification_options=[clarification_option(patient) for patient in ordered],
        warnings=warnings or [],
    )


def _ask_which(session: Session, tool: str, args: dict[str, Any], answer: str) -> Outcome:
    from app.tools.store import patients

    return _finish_clarification(session, tool, args, list(patients()), answer)


def _resume_pending(text: str, session: Session) -> tuple[str, dict[str, Any]] | None:
    pending = session.pending_clarification
    if not pending or looks_like_new_request(text):
        return None
    chosen = select_candidate(text, pending.get("candidates") or [])
    if chosen is None:
        resolved = resolve_patient(text)
        if resolved.status == "unique":
            chosen = resolved.patient
    if chosen is None:
        return None
    arguments = dict(pending.get("args") or {})
    arguments["patient_id"] = chosen["id"]
    arguments.pop("name", None)
    session.pending_clarification = None
    return str(pending["tool"]), arguments


def _reject_unconfirmed_booking(text: str, call: ToolCall, warnings: list[str]) -> ToolCall:
    """A model cannot set confirmed=true. Only the confirmation sentence can."""

    if call.name != "book_slot" or is_confirmation(text):
        return call
    warnings.append("Booking was not confirmed, so nothing was booked.")
    parsed = parse_booking(text)
    if parsed:
        return ToolCall("check_slots", parsed)
    return ToolCall("unknown", {"reason": "confirmation_required"})


def _pronoun_conflict(text: str, patient: dict[str, Any] | None) -> bool:
    pronoun = pronoun_of(text)
    if not pronoun or pronoun == "their" or patient is None:
        return False
    return pronoun != patient.get("pronoun")


def _bind_patient(call: ToolCall, session: Session, text: str) -> Outcome | None:
    """Resolve `name` to a patient id, or return a clarification outcome."""

    if call.name not in _PATIENT_TOOLS and call.name not in _REPORT_TOOLS:
        return None
    arguments = call.arguments
    name = arguments.get("name")
    patient = get_patient(arguments.get("patient_id"))
    if call.name in _REPORT_TOOLS:
        from app.tools.reports import get_report_by_id

        if arguments.get("report_id") and get_report_by_id(str(arguments.get("report_id"))) is None:
            arguments["report_id"] = None
        named = str(arguments.get("name") or "").strip()
        if named:
            resolved = resolve_patient(named)
            if resolved.status == "ambiguous":
                return _finish_clarification(
                    session,
                    call.name,
                    {key: value for key, value in arguments.items() if key != "patient_id"},
                    resolved.patients,
                    f'I found more than one patient matching "{named}". Which patient do you mean?',
                )
            if resolved.status == "none" or resolved.patient is None:
                return Outcome(
                    handled=True,
                    intent="unknown_patient",
                    answer=f'No patient matched "{named}".',
                    data=None,
                    clarification_options=all_options(),
                    needs_clarification=True,
                )
            arguments["patient_id"] = resolved.patient["id"]
            if not arguments.get("report_id"):
                latest = list_reports(resolved.patient["id"])
                if not latest:
                    return Outcome(
                        handled=True,
                        intent="missing_report",
                        answer=f"No reports found for {resolved.patient['full_name']}.",
                        data={"patient_id": resolved.patient["id"], "available_reports": []},
                    )
                arguments["report_id"] = latest[0]["id"]
            arguments.pop("name", None)
            return None
        current = get_patient(session.patient_id)
        if _pronoun_conflict(text, current):
            return _ask_which(
                session,
                call.name,
                {"question": arguments.get("question") or text},
                "The open report uses a different pronoun. Which patient do you mean?",
            )
        if session.report_id and current and not _pronoun_conflict(text, current):
            arguments["report_id"] = session.report_id
            arguments["patient_id"] = current["id"]
            return None
        if not arguments.get("report_id"):
            return _ask_which(
                session,
                call.name,
                {"question": arguments.get("question") or text, "report_type": arguments.get("report_type")},
                "Which patient's report should I use?",
            )
        return None

    if patient is None and not name and session.patient_id and call.name != "find_patient":
        patient = get_patient(session.patient_id)
        if patient:
            arguments["patient_id"] = patient["id"]
    if patient is None and name:
        resolved = resolve_patient(str(name))
        if resolved.status == "ambiguous":
            quoted = str(name).strip()
            return _finish_clarification(
                session,
                call.name,
                {key: value for key, value in arguments.items() if key != "patient_id"},
                resolved.patients,
                f'I found more than one patient matching "{quoted}". Which patient do you mean?',
            )
        if resolved.status == "none":
            return Outcome(
                handled=True,
                intent="unknown_patient",
                answer=f'No patient matched "{str(name).strip()}".',
                data=None,
                clarification_options=all_options(),
                needs_clarification=True,
            )
        patient = resolved.patient
        arguments["patient_id"] = patient["id"] if patient else None
    if call.name == "find_patient":
        return None
    if patient is None and call.name in {"get_report", "list_reports", "check_slots"}:
        return _ask_which(
            session,
            call.name,
            dict(arguments),
            "Which patient do you mean?",
        )
    if (
        call.name in _REPORT_TOOLS
        or call.name in {"get_report", "list_reports", "check_slots", "draft_clinical_report"}
    ) and patient and not arguments.get("report_id") and call.name in _REPORT_TOOLS:
        latest = list_reports(patient["id"])
        if latest:
            arguments["report_id"] = latest[0]["id"]
    arguments.pop("name", None)
    return None


def _fill_report_from_patient(call: ToolCall) -> Outcome | None:
    if call.name not in _REPORT_TOOLS or call.arguments.get("report_id"):
        return None
    patient_id = call.arguments.get("patient_id")
    if not patient_id:
        return None
    latest = list_reports(str(patient_id))
    if not latest:
        patient = get_patient(str(patient_id))
        name = patient["full_name"] if patient else patient_id
        return Outcome(
            handled=True,
            intent="missing_report",
            answer=f"No reports found for {name}.",
            data={"patient_id": patient_id, "available_reports": []},
        )
    call.arguments["report_id"] = latest[0]["id"]
    return None


_SUMMARY_OF_OPEN_REPORT = re.compile(
    r"\b(summari[sz]e|sum\s+up|summary\s+of)\b.*\b(her|his|their|the|this|that)\s+"
    r"(?:latest\s+|current\s+|open\s+)?(report|opg|iopa|cbct|bitewing|scan|x-?ray)\b",
    re.IGNORECASE,
)


def _route_open_report_summary(text: str, call: ToolCall, session: Session) -> ToolCall:
    """'Summarize her report' in a session with a patient in context always summarizes.

    Models sometimes answer this with list_reports. The open report wins; with
    only a patient in context, that patient's latest report is used. A newly
    named patient still goes through normal resolution.
    """

    if not _SUMMARY_OF_OPEN_REPORT.search(text) or extract_name(text):
        return call
    if session.report_id:
        if call.name == "summarize_report" and call.arguments.get("report_id") == session.report_id:
            return call
        return ToolCall("summarize_report", {"report_id": session.report_id, "pronoun": pronoun_of(text)})
    if session.patient_id:
        latest = list_reports(session.patient_id)
        if latest:
            return ToolCall("summarize_report", {"report_id": latest[0]["id"], "pronoun": pronoun_of(text)})
    return call


_LISTING_WORDS = re.compile(r"\b(list|which|what|all|any)\b|\breports\b", re.IGNORECASE)
_OPEN_ONE = re.compile(r"\b(open|show|get|fetch|view|display|retrieve|pull\s+up)\b", re.IGNORECASE)


def _route_open_single_report(text: str, call: ToolCall) -> ToolCall:
    """'Show me Priya Sharma's OPG' asks for one report, not the list of reports."""

    if call.name != "list_reports" or _LISTING_WORDS.search(text) or not _OPEN_ONE.search(text):
        return call
    report_type = detect_report_type(text)
    if not report_type and not re.search(r"\breport\b", text, re.IGNORECASE):
        return call
    arguments = {
        "name": call.arguments.get("name") or extract_name(text),
        "patient_id": call.arguments.get("patient_id"),
        "report_type": report_type or call.arguments.get("report_type"),
        "which": which_report(text),
    }
    return ToolCall("get_report", {key: value for key, value in arguments.items() if value})


def greeting_outcome() -> Outcome:
    """Small talk gets a friendly reply. No tool runs and the session is left as it was."""

    return Outcome(handled=True, intent="greeting", answer=GREETING_REPLY)


def validate_call(call: ToolCall, text: str, session: Session, role: str) -> Outcome:
    """Apply allow-list, confirmation, patient resolution, and schema checks.

    `role` is accepted so a future rule can refuse assistant actions here.
    Assistants may book only after the confirmation sentence, which is enforced
    by rewriting any other book_slot call.
    """

    del role  # Authorization for approval lives on the approve route.
    if is_greeting(text):
        return greeting_outcome()
    warnings: list[str] = []
    resumed = _resume_pending(text, session)
    if looks_like_new_request(text):
        session.pending_clarification = None
    if session.pending_clarification and resumed is None and not looks_like_new_request(text) and not is_confirmation(text):
        pending = session.pending_clarification
        return _finish_clarification(
            session,
            str(pending["tool"]),
            dict(pending.get("args") or {}),
            list(pending.get("candidates") or []),
            "I still need you to choose one of these patients.",
        )
    if resumed is not None:
        call = ToolCall(resumed[0], resumed[1])
    elif is_confirmation(text):
        pending_booking = session.pending_booking
        if not pending_booking:
            return Outcome(
                handled=True,
                intent="unknown",
                answer="There is no scan waiting for confirmation.",
            )
        call = ToolCall(
            "book_slot",
            {
                "slot_id": pending_booking["slot_id"],
                "patient_id": pending_booking["patient_id"],
                "confirmed": True,
            },
        )
    else:
        call = _reject_unconfirmed_booking(text, call, warnings)
        call = _route_open_report_summary(text, call, session)
        call = _route_open_single_report(text, call)

    if call.name == "unknown" or call.name not in ALLOWED_TOOLS:
        if call.arguments.get("reason") == "confirmation_required":
            return Outcome(
                handled=True,
                intent="propose_booking",
                answer="I need an explicit confirmation before I book a slot. Nothing was booked.",
                warnings=warnings,
            )
        return Outcome(
            handled=True,
            intent="unknown",
            answer=(
                "I can open a report, summarize it, answer a question about the open report, "
                "draft a report from dictation, or book a scan."
            ),
            warnings=warnings,
        )

    if call.name == "check_slots":
        spoken_booking = parse_booking(text)
        if spoken_booking:
            # The demo clock, not the model's guess, decides "tomorrow".
            call.arguments["date_from"] = spoken_booking.get("date_from")
            call.arguments["date_to"] = spoken_booking.get("date_to")
            call.arguments["part_of_day"] = spoken_booking.get("part_of_day")
            if spoken_booking.get("scan_type"):
                call.arguments["scan_type"] = spoken_booking["scan_type"]
            if spoken_booking.get("slot_id"):
                call.arguments["slot_id"] = spoken_booking["slot_id"]
            if spoken_booking.get("name"):
                call.arguments["name"] = spoken_booking["name"]
                call.arguments.pop("patient_id", None)

    if call.name == "get_report":
        which = str(call.arguments.get("which") or "latest").lower()
        call.arguments["which"] = "oldest" if which == "oldest" else "latest"
        if call.arguments.get("report_type"):
            call.arguments["report_type"] = canonical_report_type(str(call.arguments["report_type"]))
    if call.name == "check_slots" and call.arguments.get("scan_type"):
        call.arguments["scan_type"] = canonical_report_type(str(call.arguments["scan_type"]))
    if call.name == "check_slots" and call.arguments.get("slot_id"):
        call.arguments["slot_id"] = str(call.arguments["slot_id"]).upper()

    clarification = _bind_patient(call, session, text)
    if clarification is not None:
        clarification.warnings = warnings + clarification.warnings
        return clarification
    missing_report = _fill_report_from_patient(call)
    if missing_report is not None:
        missing_report.warnings = warnings
        return missing_report

    if call.name == "check_slots" and not call.arguments.get("scan_type") and not call.arguments.get("slot_id"):
        return Outcome(
            handled=True,
            intent="propose_booking",
            answer="Which scan should I book: OPG, CBCT, or IOPA?",
            needs_clarification=True,
            warnings=warnings,
        )

    model = TOOL_ARG_MODELS[call.name]
    try:
        parsed = model.model_validate(call.arguments)
    except ValidationError as exc:
        return Outcome(
            handled=True,
            intent="unknown",
            answer="I couldn't use that request. " + "; ".join(error["msg"] for error in exc.errors()),
            warnings=warnings,
        )
    arguments = parsed.model_dump()
    patient = get_patient(arguments.get("patient_id"))
    return Outcome(
        handled=False,
        tool_name=call.name,
        arguments=arguments,
        patient=patient,
        warnings=warnings,
    )
