"""Deterministic interpreter used in tests and whenever a hosted model is unavailable."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.config import get_settings
from app.llm.base import ToolCall
from app.validation.grounding import hedge_in
from app.validation.report_types import detect_report_type

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_NAME_STOP = {
    "tomorrow", "today", "morning", "afternoon", "evening", "tonight", "on", "at",
    "next", "this", "please", "slot", "the", "a", "an", "opg", "iopa", "cbct",
    "bitewing", "panoramic", "pano", "orthopantomogram", "report", "reports",
    "latest", "newest", "last", "oldest", "scan", "appointment",
    "his", "her", "their", "him", "she", "he",
    *_WEEKDAYS,
}
_HOW = {
    "horizontally": "horizontal",
    "horizontal": "horizontal",
    "vertically": "vertical",
    "vertical": "vertical",
    "mesioangular": "mesioangular",
    "mesioangularly": "mesioangular",
    "mesio-angular": "mesioangular",
    "distoangular": "distoangular",
    "distoangularly": "distoangular",
    "disto-angular": "distoangular",
}
_SITE_RE = re.compile(
    r"\b((?:upper|lower|maxillary|mandibular)\s+(?:left|right)\s+"
    r"(?:(?:first|second|third|1st|2nd|3rd)\s+)?"
    r"(?:molar|premolar|canine|incisor|wisdom(?:\s+tooth)?|bicuspid))\b",
    re.IGNORECASE,
)
_IMPACTION_RE = re.compile(
    r"(?P<site>(?:upper|lower|maxillary|mandibular)\s+(?:left|right)\s+"
    r"(?:(?:first|second|third|1st|2nd|3rd)\s+)?"
    r"(?:molar|premolar|canine|incisor|wisdom(?:\s+tooth)?|bicuspid))"
    r".{0,80}?"
    r"(?P<how>horizontally|mesioangular(?:ly)?|distoangular(?:ly)?|vertically|vertical|horizontal)?"
    r"\s*(?:impacted|impaction)\b",
    re.IGNORECASE,
)
_CARIES_RE = re.compile(
    r"\b(?P<hedge>maybe|possibly|possible|might|could\s+be|looks\s+like)?\s*"
    r"caries\b(?:\s+on\s+(?:the\s+)?)?(?P<site>[a-z0-9][a-z0-9 \-]*)?",
    re.IGNORECASE,
)


_FDI_RE = re.compile(r"(?:\b(?:tooth|fdi)\s*#?\s*|#\s*|\b)([1-4][1-8])\b", re.IGNORECASE)


def find_fdi(text: str) -> str | None:
    """A spoken FDI number such as 'tooth 36' or '#36'. Only 11-18, 21-28, 31-38, 41-48."""

    labeled = re.search(r"(?:\b(?:tooth|fdi)\s*#?\s*|#\s*)([1-4][1-8])\b", text, re.IGNORECASE)
    if labeled:
        return labeled.group(1)
    bare = _FDI_RE.search(text)
    return bare.group(1) if bare else None


_GREETING_RE = re.compile(
    r"(hi|hello|hey|hiya|howdy|yo|greetings|good\s+(morning|afternoon|evening|day)|"
    r"thanks|thank\s+you|thanks\s+a\s+lot|thank\s+you\s+so\s+much|cheers|"
    r"how\s+are\s+you|how\s+are\s+you\s+doing|what'?s\s+up)"
    r"(\s+(there|team|doc|doctor|viscan|everyone|again))?",
    re.IGNORECASE,
)

GREETING_REPLY = (
    "Hello! I'm your dental assistant. I can open patient reports, turn dictation into a "
    "draft report, summarize or answer questions about a report, and book scans. "
    'Try "Open Priya\'s latest OPG report".'
)


def is_greeting(text: str) -> bool:
    """True when the whole message is a greeting or small talk, never a name or request."""

    cleaned = re.sub(r"[\s.,!?:;)(-]+", " ", text or "").strip()
    if not cleaned:
        return False
    parts = re.split(r"\s*(?:,|\band\b)\s*|\s+(?=(?:hi|hello|hey|thanks|thank|good|how)\b)", cleaned, flags=re.I)
    parts = [part for part in parts if part.strip()]
    return all(_GREETING_RE.fullmatch(part.strip()) for part in parts)


def is_confirmation(text: str) -> bool:
    """True only for an explicit confirmation such as 'yes, confirm'."""

    lowered = text.strip().lower().rstrip(".!")
    return bool(
        re.fullmatch(
            r"(yes(\s*,\s*|\s+)confirm(ed)?|yes|yep|yeah|confirm|confirmed|yes please|go ahead|book it)",
            lowered,
        )
    )


def looks_like_new_request(text: str) -> bool:
    if is_confirmation(text):
        return False
    return bool(
        re.search(
            r"\b(open|show|get|fetch|view|display|retrieve|book|summarize|summarise|draft|list|find)\b",
            text,
            re.IGNORECASE,
        )
    )


def is_summary(text: str) -> bool:
    return bool(re.search(r"\b(summarise|summarize|summary|sum up)\b", text, re.IGNORECASE))


def is_question(text: str) -> bool:
    if is_summary(text) or re.search(r"\b(open|show|book|draft)\b", text, re.IGNORECASE):
        return False
    lowered = text.strip().lower()
    if re.search(r"\bwhat reports?\b", lowered) or (
        re.search(r"\b(list|which)\b", lowered) and re.search(r"\breports?\b", lowered)
    ):
        return False
    return bool(re.match(r"^(does|do|is|are|has|have|did|what|which|who|any|can|could)\b", lowered)) or lowered.endswith("?")


def is_dictation(text: str) -> bool:
    if looks_like_new_request(text) or is_question(text) or is_summary(text):
        return False
    return bool(
        re.search(
            r"\b(impacted|impaction|caries|carious|radiolucency|radiolucent|periapical|"
            r"mesioangular|distoangular|horizontally|vertically|bone\s+loss|fracture|lesion)\b",
            text,
            re.IGNORECASE,
        )
    )


def pronoun_of(text: str) -> str | None:
    match = re.search(r"\b(her|his|their|she|he|him)\b", text, re.IGNORECASE)
    if not match:
        return None
    word = match.group(1).lower()
    if word in {"her", "she"}:
        return "her"
    if word in {"his", "he", "him"}:
        return "his"
    return "their"


# Command words that often sit in front of a spoken name ("show me pryia sharma's opg").
_FILLER = {"show", "me", "open", "get", "pull", "up", "please", "the", "latest", "report"}


def strip_filler(raw: str) -> str:
    """Drop leading command and filler words before a name is read."""

    tokens = raw.split()
    while tokens and tokens[0].lower().strip(".,") in _FILLER:
        tokens.pop(0)
    return " ".join(tokens)


def _trim_name(raw: str) -> str:
    kept: list[str] = []
    for token in strip_filler(raw).split():
        if token.lower().strip(".,") in _NAME_STOP:
            break
        kept.append(token.strip(".,"))
    return " ".join(kept).strip()


def extract_name(text: str) -> str | None:
    """Pull a patient name out of an utterance. Returns None when nobody is named."""

    possessive = re.search(
        r"\b(?:open|show|get|fetch|view|display|retrieve|for|about|of|book|summarize|summarise|summary)\s+"
        r"([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){0,3}?)(?:'s|’s)\b",
        text,
        re.IGNORECASE,
    )
    if possessive:
        name = _trim_name(possessive.group(1))
        if name:
            return name
    spoken = re.search(
        r"\b(?:summarize|summarise|summary of|sum up|open|show|get)\s+"
        r"([A-Za-z][A-Za-z'\-]+)\s+(?:latest\s+|newest\s+|oldest\s+)?"
        r"(?:opg|iopa|cbct|bitewing|pano|panoramic|report)\b",
        text,
        re.IGNORECASE,
    )
    if spoken:
        name = _trim_name(spoken.group(1))
        if name and name.lower() not in _NAME_STOP:
            return name
    for_name = re.search(r"\bfor\s+([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){0,2})", text)
    if for_name:
        name = _trim_name(for_name.group(1))
        if name and name.lower() not in _NAME_STOP:
            return name
    return None


def which_report(text: str) -> str:
    if re.search(r"\b(oldest|earliest|first report)\b", text, re.IGNORECASE):
        return "oldest"
    return "latest"


def _parse_when(text: str) -> tuple[str | None, str | None, str | None]:
    demo = get_settings().demo_date
    lowered = text.lower()
    part = None
    if re.search(r"\bmorning\b", lowered):
        part = "morning"
    elif re.search(r"\bafternoon\b", lowered):
        part = "afternoon"
    elif re.search(r"\b(evening|tonight)\b", lowered):
        part = "evening"
    target: date | None = None
    if "tomorrow" in lowered:
        target = demo + timedelta(days=1)
    elif re.search(r"\btoday\b", lowered):
        target = demo
    else:
        for index, weekday in enumerate(_WEEKDAYS):
            if re.search(rf"\b{weekday}\b", lowered):
                delta = (index - demo.weekday()) % 7
                if delta == 0:
                    delta = 7
                target = demo + timedelta(days=delta)
                break
        if target is None:
            iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
            if iso:
                target = date.fromisoformat(iso.group(1))
    if target is not None:
        return target.isoformat(), target.isoformat(), part
    start = demo + timedelta(days=1)
    end = demo + timedelta(days=7)
    return start.isoformat(), end.isoformat(), part


def parse_booking(text: str) -> dict[str, Any] | None:
    if not re.search(r"\bbook\b", text, re.IGNORECASE):
        return None
    slot_match = re.search(r"\bslot\s+([A-Za-z]?\d{2,4})\b", text, re.IGNORECASE)
    date_from, date_to, part = _parse_when(text)
    return {
        "scan_type": detect_report_type(text),
        "date_from": date_from,
        "date_to": date_to,
        "part_of_day": part,
        "name": extract_name(text),
        "slot_id": slot_match.group(1).upper() if slot_match else None,
    }


def _clean_sentence(sentence: str) -> str:
    return sentence.strip().strip('"').strip()


def _parse_sentence(sentence: str) -> dict[str, Any] | None:
    text = _clean_sentence(sentence)
    if not text:
        return None
    impaction = _IMPACTION_RE.search(text)
    if impaction:
        how = (impaction.group("how") or "").lower()
        site = re.sub(r"\s+", " ", impaction.group("site")).strip()
        return {
            "finding": text.rstrip("."),
            "anatomical_site": {"description": site},
            "classification": _HOW.get(how, "impaction"),
            "certainty": "uncertain" if hedge_in(text) else "stated",
            "evidence_span": text if text in sentence or text in sentence.strip() else sentence.strip(),
        }
    fdi = find_fdi(text)
    caries = _CARIES_RE.search(text)
    if caries:
        site = re.sub(r"\s+", " ", (caries.group("site") or "")).strip(" .,-")
        if not site and fdi:
            site = f"tooth {fdi}"
        description = site or "unspecified site"
        finding = f"caries on the {description}" if site else "caries"
        return {
            "finding": finding if finding.lower() in text.lower() else text.rstrip("."),
            "anatomical_site": {"description": description},
            "classification": "caries",
            "certainty": "uncertain" if hedge_in(text) else "stated",
            "evidence_span": text,
        }
    site_match = _SITE_RE.search(text)
    if site_match and re.search(r"\b(lesion|fracture|missing|restoration|radiolucency|unerupted|bone\s+loss)\b", text, re.I):
        return {
            "finding": text.rstrip("."),
            "anatomical_site": {"description": site_match.group(1)},
            "classification": None,
            "certainty": "uncertain" if hedge_in(text) else "stated",
            "evidence_span": text,
        }
    if fdi and re.search(r"\b(lesion|fracture|missing|restoration|radiolucency|unerupted|impacted|bone\s+loss)\b", text, re.I):
        return {
            "finding": text.rstrip("."),
            "anatomical_site": {"description": f"tooth {fdi}"},
            "classification": None,
            "certainty": "uncertain" if hedge_in(text) else "stated",
            "evidence_span": text,
        }
    return None


def extract_transcript(prompt_or_text: str) -> str:
    match = re.search(r"TRANSCRIPT_START\n(.*?)\nTRANSCRIPT_END", prompt_or_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return prompt_or_text.strip()


def extract_findings(transcript: str) -> dict[str, Any]:
    """Rule-based finding extractor for short clinical sentences."""

    parts = re.split(r"(?<=[.!?])\s+|\n+", transcript.strip())
    sentences = [part.strip() for part in parts if part.strip()] or [transcript.strip()]
    findings = []
    for sentence in sentences:
        parsed = _parse_sentence(sentence)
        if parsed:
            # Evidence has to be an exact slice of the original transcript.
            if parsed["evidence_span"] not in transcript:
                parsed["evidence_span"] = sentence if sentence in transcript else transcript
            findings.append(parsed)
    if not findings:
        parsed = _parse_sentence(transcript.strip())
        if parsed:
            if parsed["evidence_span"] not in transcript:
                parsed["evidence_span"] = transcript.strip()
            findings.append(parsed)
    return {"findings": findings}


class RuleBasedProvider:
    """Regex and fuzzy-name interpreter. It never calls the network."""

    name = "rule"

    def interpret(self, text: str, context: dict[str, Any], tools: list[dict[str, Any]]) -> ToolCall:
        raw = text.strip()
        if is_greeting(raw):
            return ToolCall("unknown", {"utterance": raw, "reason": "greeting"})
        pending_booking = context.get("pending_booking") or None
        if pending_booking and is_confirmation(raw):
            return ToolCall(
                "book_slot",
                {
                    "slot_id": pending_booking["slot_id"],
                    "patient_id": pending_booking["patient_id"],
                    "confirmed": True,
                },
            )
        pending = context.get("pending_clarification") or None
        if pending and not looks_like_new_request(raw):
            arguments = dict(pending.get("args") or {})
            arguments["name"] = raw
            arguments.pop("patient_id", None)
            return ToolCall(str(pending.get("tool") or "unknown"), arguments)
        if is_confirmation(raw):
            return ToolCall("unknown", {"utterance": raw, "reason": "nothing_to_confirm"})
        booking = parse_booking(raw)
        if booking:
            return ToolCall("check_slots", booking)
        if re.search(r"\bwhat reports?\b", raw, re.I) or (
            re.search(r"\b(list|which)\b", raw, re.I) and re.search(r"\breports?\b", raw, re.I)
        ):
            return ToolCall(
                "list_reports",
                {"name": extract_name(raw), "report_type": detect_report_type(raw)},
            )
        if is_summary(raw):
            return ToolCall(
                "summarize_report",
                {
                    "report_id": "" if extract_name(raw) else (context.get("report_id") or ""),
                    "pronoun": pronoun_of(raw),
                    "name": extract_name(raw),
                },
            )
        if is_question(raw):
            return ToolCall(
                "answer_report_question",
                {
                    "report_id": context.get("report_id") or "",
                    "question": raw,
                    "pronoun": pronoun_of(raw),
                },
            )
        if re.search(r"\b(open|show|get|fetch|view|display|retrieve|pull)\b", raw, re.I) and (
            re.search(r"\breport\b", raw, re.I) or detect_report_type(raw)
        ):
            return ToolCall(
                "get_report",
                {
                    "name": extract_name(raw),
                    "report_type": detect_report_type(raw),
                    "which": which_report(raw),
                },
            )
        if is_dictation(raw):
            return ToolCall("draft_clinical_report", {"transcript": raw, "name": extract_name(raw)})
        if re.search(r"\bfind\b", raw, re.I):
            return ToolCall("find_patient", {"name": extract_name(raw) or raw})
        return ToolCall("unknown", {"utterance": raw})

    def generate(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        return extract_findings(extract_transcript(prompt))
