"""Interpret, validate, execute, and phrase the reply. The model never touches the records."""

from __future__ import annotations

import time
from typing import Any

from app.llm.base import ToolCall
from app.logging_utils import get_logger
from app.schemas import UnifiedResponse
from app.session import Session, session_store
from app.tools.booking import get_slot
from app.tools.dictation import create_draft
from app.tools.patients import get_patient, public_patient
from app.tools.registry import execute_tool, tool_schemas
from app.tools.reports import report_summary
from app.llm.rule_based import is_greeting
from app.validation.rules import Outcome, greeting_outcome, validate_call

logger = get_logger()


def build_context(session: Session) -> dict[str, Any]:
    """Context the interpreter may see. It is not written to the logs."""

    patient = get_patient(session.patient_id)
    return {
        "patient_id": session.patient_id,
        "patient_name": patient["full_name"] if patient else None,
        "pronoun": patient["pronoun"] if patient else None,
        "report_id": session.report_id,
        "pending_clarification": session.pending_clarification,
        "pending_booking": session.pending_booking,
    }


def _source(
    report_id: str | None = None,
    patient_id: str | None = None,
    fields: list[str] | None = None,
    quotes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "patient_id": patient_id,
        "fields": fields or [],
        "quotes": [quote for quote in (quotes or []) if quote],
    }


def _pack(
    session: Session,
    *,
    intent: str,
    answer: str,
    provider_used: str,
    data: Any = None,
    sources: list[dict[str, Any]] | None = None,
    needs_clarification: bool = False,
    clarification_options: list[dict[str, Any]] | None = None,
    requires_clinician_review: bool = False,
    warnings: list[str] | None = None,
    stt_provider: str | None = None,
    transcript: str | None = None,
    started: float,
) -> dict[str, Any]:
    patient_id = None
    if isinstance(data, dict):
        patient_id = data.get("patient_id") or (data.get("patient") or {}).get("id")
    logger.info(
        "handled session=%s intent=%s patient_id=%s provider=%s",
        session.id,
        intent,
        patient_id or session.patient_id or "-",
        provider_used,
    )
    payload = UnifiedResponse(
        session_id=session.id,
        intent=intent,
        answer=answer,
        data=data,
        sources=sources or [],
        needs_clarification=needs_clarification,
        clarification_options=clarification_options or [],
        requires_clinician_review=requires_clinician_review,
        provider_used=provider_used,
        stt_provider=stt_provider,
        transcript=transcript,
        latency_ms=int((time.perf_counter() - started) * 1000),
        warnings=warnings or [],
    )
    return payload.model_dump()


def _from_outcome(
    session: Session,
    outcome: Outcome,
    provider_used: str,
    started: float,
    stt_provider: str | None = None,
    transcript: str | None = None,
) -> dict[str, Any]:
    return _pack(
        session,
        intent=outcome.intent,
        answer=outcome.answer,
        provider_used=provider_used,
        data=outcome.data,
        sources=outcome.sources,
        needs_clarification=outcome.needs_clarification,
        clarification_options=outcome.clarification_options,
        requires_clinician_review=outcome.requires_clinician_review,
        warnings=outcome.warnings,
        stt_provider=stt_provider,
        transcript=transcript,
        started=started,
    )


def _render_report(session: Session, result: dict[str, Any]) -> tuple[str, str, Any, list[dict[str, Any]]]:
    if not result.get("found"):
        patient = result.get("patient") or {}
        available = result.get("available_reports") or []
        requested = result.get("requested_type") or "matching"
        name = patient.get("full_name") or result.get("patient_id") or "that patient"
        if patient:
            session.patient_id = patient.get("id")
        session.report_id = None
        session.pending_clarification = None
        if available:
            listing = ", ".join(f"{item['type']} ({item['date']}, {item['id']})" for item in available)
            answer = f"No {requested} report found for {name}. Available reports: {listing}."
        else:
            answer = f"No {requested} report found for {name}."
        sources = [
            _source(item["id"], item["patient_id"], ["type", "date"])
            for item in available
        ]
        data = {
            "patient_id": patient.get("id"),
            "patient": patient or None,
            "requested_type": result.get("requested_type"),
            "available_reports": available,
            "report": None,
        }
        return "missing_report", answer, data, sources

    report = result["report"]
    patient = result["patient"]
    session.patient_id = patient["id"]
    session.report_id = report["id"]
    session.pending_clarification = None
    session.pending_booking = None
    finding_lines = []
    quotes = []
    for finding in report.get("findings") or []:
        tooth = f" (FDI {finding['fdi_tooth']})" if finding.get("fdi_tooth") else ""
        finding_lines.append(f"- {finding.get('description')}{tooth}")
        if finding.get("description"):
            quotes.append(finding["description"])
    if report.get("impression"):
        quotes.append(report["impression"])
    which = result.get("which") or "latest"
    answer = (
        f"{patient['full_name']}'s {which} {report['type']} report is {report['id']} "
        f"dated {report['date']}.\n"
        f"Clinician: {report['clinician']}\n"
        f"Findings:\n" + ("\n".join(finding_lines) or "- None recorded.") + "\n"
        f"Impression: {report['impression']}"
    )
    data = {
        "found": True,
        "patient_id": patient["id"],
        "patient": patient,
        "report": report,
        "which": which,
    }
    sources = [
        _source(
            report["id"],
            patient["id"],
            ["type", "date", "findings", "impression", "recommendations"],
            quotes,
        )
    ]
    return "retrieve_report", answer, data, sources


def _render_summary(session: Session, result: dict[str, Any]) -> tuple[str, str, Any, list[dict[str, Any]]]:
    if not result.get("found"):
        return (
            "missing_report",
            "I don't have that report open. Tell me which patient to open first.",
            None,
            [],
        )
    report = result["report"]
    patient = result.get("patient") or {}
    session.patient_id = patient.get("id") or report["patient_id"]
    session.report_id = report["id"]
    session.pending_clarification = None
    data = {
        "patient_id": session.patient_id,
        "report_id": report["id"],
        "summary": result["summary"],
        "report": report_summary(report),
    }
    sources = [_source(report["id"], session.patient_id, result.get("fields"), result.get("quotes"))]
    return "summarize_report", result["summary"], data, sources


def _render_answer(session: Session, result: dict[str, Any]) -> tuple[str, str, Any, list[dict[str, Any]]]:
    if not result.get("found"):
        return (
            "answer_question",
            "I don't have a report open to answer from.",
            None,
            [],
        )
    summary = result["report"]
    patient = result.get("patient") or {}
    session.patient_id = patient.get("id") or summary["patient_id"]
    session.report_id = summary["id"]
    data = {
        "patient_id": session.patient_id,
        "report_id": summary["id"],
        "stated": result.get("stated", False),
        "report": summary,
    }
    sources = [
        _source(summary["id"], session.patient_id, result.get("fields") or [], result.get("quotes") or [])
    ]
    return "answer_question", result["answer"], data, sources


def _render_booking(
    session: Session,
    arguments: dict[str, Any],
    result: dict[str, Any],
    patient: dict[str, Any] | None,
) -> tuple[str, str, Any, list[dict[str, Any]]]:
    slot_id = (arguments.get("slot_id") or "").upper() or None
    if slot_id:
        chosen = get_slot(slot_id)
        if chosen is None:
            return (
                "booking_unavailable",
                f"I couldn't find slot {slot_id}.",
                {"booked": False, "slot_id": slot_id},
                [],
            )
        if chosen["booked"]:
            return (
                "booking_unavailable",
                f"Slot {chosen['id']} is already booked. I did not book it again.",
                {"booked": False, "slot": chosen, "reason": "already_booked"},
                [],
            )
        pool = [chosen]
    else:
        pool = [slot for slot in result.get("slots") or [] if not slot["booked"]]
        if not pool:
            scan = arguments.get("scan_type") or "scan"
            return (
                "booking_unavailable",
                f"No available {scan} slots in that window. I did not book anything.",
                {"booked": False, "slots": result.get("slots") or []},
                [],
            )
    slot = pool[0]
    if patient is None:
        patient = get_patient(arguments.get("patient_id"))
    if patient is None:
        return ("unknown_patient", "Which patient should I book this for?", None, [])
    session.patient_id = patient["id"]
    session.pending_booking = {
        "slot_id": slot["id"],
        "patient_id": patient["id"],
        "scan_type": slot["scan_type"],
        "date": slot["date"],
        "time": slot["time"],
    }
    session.pending_clarification = None
    scan_type = str(slot["scan_type"])
    article = "an" if scan_type[:1].lower() in "aeiou" else "a"
    answer = (
        f"I can book {article} {scan_type} for {patient['full_name']} on {slot['date']} "
        f"at {slot['time']} (slot {slot['id']}). Say \"yes, confirm\" to book it. "
        "I have not booked it yet."
    )
    data = {
        "booked": False,
        "patient_id": patient["id"],
        "patient": public_patient(patient),
        "proposed_slot": slot,
    }
    return "propose_booking", answer, data, []


def _render_confirmed(session: Session, result: dict[str, Any]) -> tuple[str, str, Any, list[dict[str, Any]]]:
    slot = result.get("slot") or {}
    patient = get_patient(result.get("patient_id") or slot.get("patient_id"))
    name = patient["full_name"] if patient else (result.get("patient_id") or "the patient")
    if result.get("booked"):
        session.pending_booking = None
        if patient:
            session.patient_id = patient["id"]
        answer = (
            f"Booked {slot.get('scan_type')} for {name} on {slot.get('date')} "
            f"at {slot.get('time')} (slot {slot.get('id')})."
        )
        return "confirm_booking", answer, {"booked": True, "patient_id": patient["id"] if patient else None, "slot": slot}, []
    if result.get("reason") == "already_booked":
        session.pending_booking = None
        return (
            "booking_unavailable",
            f"Slot {slot.get('id') or result.get('slot_id')} is already booked. I did not book it again.",
            {"booked": False, "reason": "already_booked", "slot": slot or None},
            [],
        )
    return (
        "propose_booking",
        "I have not booked that slot. Say \"yes, confirm\" after I propose one.",
        {"booked": False, "reason": result.get("reason")},
        [],
    )


def _render_draft(session: Session, draft: dict[str, Any]) -> tuple[str, str, Any, list[dict[str, Any]], bool]:
    if draft.get("patient_id"):
        session.patient_id = draft["patient_id"]
    session.pending_clarification = None
    quotes = [finding.get("evidence_span") or "" for finding in draft.get("findings") or []]
    sources = [_source(draft["report_id"], draft.get("patient_id"), ["transcript", "findings"], quotes)]
    return "draft_report", draft["draft_text"], draft, sources, True


def _render_list(session: Session, result: dict[str, Any], patient: dict[str, Any] | None) -> tuple[str, str, Any, list[dict[str, Any]]]:
    rows = result.get("reports") or []
    if patient:
        session.patient_id = patient["id"]
    if not rows:
        name = patient["full_name"] if patient else "that patient"
        return "list_reports", f"No reports found for {name}.", {"reports": [], "patient_id": patient["id"] if patient else None}, []
    lines = [f"- {row['type']} {row['id']} ({row['date']})" for row in rows]
    name = patient["full_name"] if patient else rows[0]["patient_id"]
    sources = [_source(row["id"], row["patient_id"], ["type", "date"]) for row in rows]
    return "list_reports", f"Reports for {name}:\n" + "\n".join(lines), {"reports": rows, "patient_id": patient["id"] if patient else None}, sources


def _render_found_patient(session: Session, result: dict[str, Any]) -> tuple[str, str, Any, list[dict[str, Any]]]:
    people = result.get("patients") or []
    if result.get("status") == "unique" and people:
        session.patient_id = people[0]["id"]
        person = people[0]
        answer = (
            f"{person['full_name']} ({person['id']}), born {person['dob_year']}, "
            f"last visit {person['last_visit']}."
        )
        return "find_patient", answer, {"patient": person, "patient_id": person["id"]}, []
    if result.get("status") == "none":
        return "unknown_patient", "No patient matched that name.", None, []
    return "clarify_patient", "I found more than one matching patient.", {"patients": people}, []


def handle_text(
    session_id: str | None,
    text: str,
    role: str,
    stt_provider: str | None = None,
    transcript: str | None = None,
) -> dict[str, Any]:
    """Run one typed (or already transcribed) turn."""

    started = time.perf_counter()
    session = session_store.get(session_id)
    from app.llm.router import get_llm_router

    if is_greeting(text):
        # Greetings never reach a model, so "hi" cannot be read as a patient name.
        return _from_outcome(session, greeting_outcome(), "rule", started, stt_provider, transcript)
    router = get_llm_router()
    call, provider_used = router.interpret(text, build_context(session), tool_schemas())
    if not isinstance(call, ToolCall):
        call = ToolCall("unknown", {})
    logger.info("interpreted session=%s tool=%s provider=%s", session.id, call.name, provider_used)
    outcome = validate_call(call, text, session, role)
    warnings = list(outcome.warnings)
    if router.used_fallback:
        warnings.append("Primary LLM provider failed; used the deterministic rule interpreter.")
    if outcome.handled:
        outcome.warnings = warnings
        return _from_outcome(session, outcome, provider_used, started, stt_provider, transcript)

    if outcome.tool_name == "draft_clinical_report":
        draft, draft_provider, fell_back = create_draft(
            outcome.arguments["transcript"], outcome.arguments.get("patient_id")
        )
        provider_used = "rule" if fell_back else draft_provider
        if fell_back and not any("deterministic rule interpreter" in item for item in warnings):
            warnings.append("Primary LLM provider failed; used the deterministic rule interpreter.")
        intent, answer, data, sources, review = _render_draft(session, draft)
        warnings.extend(draft.get("warnings") or [])
        return _pack(
            session,
            intent=intent,
            answer=answer,
            provider_used=provider_used,
            data=data,
            sources=sources,
            requires_clinician_review=review,
            warnings=warnings,
            stt_provider=stt_provider,
            transcript=transcript,
            started=started,
        )

    result = execute_tool(outcome.tool_name, outcome.arguments)
    if outcome.tool_name == "get_report":
        intent, answer, data, sources = _render_report(session, result)
    elif outcome.tool_name == "summarize_report":
        intent, answer, data, sources = _render_summary(session, result)
    elif outcome.tool_name == "answer_report_question":
        intent, answer, data, sources = _render_answer(session, result)
    elif outcome.tool_name == "check_slots":
        intent, answer, data, sources = _render_booking(session, outcome.arguments, result, outcome.patient)
    elif outcome.tool_name == "book_slot":
        intent, answer, data, sources = _render_confirmed(session, result)
    elif outcome.tool_name == "list_reports":
        intent, answer, data, sources = _render_list(session, result, outcome.patient)
    elif outcome.tool_name == "find_patient":
        intent, answer, data, sources = _render_found_patient(session, result)
    else:
        intent, answer, data, sources = ("unknown", "I couldn't complete that request.", None, [])
    review = False
    return _pack(
        session,
        intent=intent,
        answer=answer,
        provider_used=provider_used,
        data=data,
        sources=sources,
        requires_clinician_review=review,
        warnings=warnings,
        stt_provider=stt_provider,
        transcript=transcript or (text if stt_provider else None),
        started=started,
    )


def handle_dictation(
    session_id: str | None,
    transcript: str,
    patient_id: str | None,
    role: str,
    stt_provider: str | None = None,
) -> dict[str, Any]:
    """Draft a report from a transcript without asking the interpreter to pick a tool."""

    del role
    started = time.perf_counter()
    session = session_store.get(session_id)
    draft, provider_used, fell_back = create_draft(transcript, patient_id)
    warnings = list(draft.get("warnings") or [])
    if fell_back:
        provider_used = "rule"
        warnings.append("Primary LLM provider failed; used the deterministic rule interpreter.")
    intent, answer, data, sources, review = _render_draft(session, draft)
    return _pack(
        session,
        intent=intent,
        answer=answer,
        provider_used=provider_used,
        data=data,
        sources=sources,
        requires_clinician_review=review,
        warnings=warnings,
        stt_provider=stt_provider,
        transcript=transcript,
        started=started,
    )
