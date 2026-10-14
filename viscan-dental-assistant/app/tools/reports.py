"""Read-only report queries over the mock chart."""

from __future__ import annotations

from typing import Any

from app.tools.patients import get_patient, public_patient
from app.tools.store import reports
from app.validation.grounding import normalize, term_supported
from app.validation.report_types import canonical_report_type

_QUESTION_STOPWORDS = {
    "does", "do", "did", "is", "are", "was", "were", "has", "have", "had",
    "she", "he", "her", "his", "their", "they", "the", "a", "an", "patient",
    "any", "there", "what", "which", "who", "on", "in", "of", "to", "for",
    "and", "or", "with", "about", "report", "reports", "this", "that",
    "please", "me", "tell", "show", "can", "could", "would", "should",
}


def list_reports(patient_id: str, report_type: str | None = None) -> list[dict[str, Any]]:
    """Return a patient's reports, newest first, optionally filtered by type."""

    canonical = canonical_report_type(report_type)
    matched = [report for report in reports() if report["patient_id"] == patient_id]
    if canonical:
        matched = [report for report in matched if report["type"] == canonical]
    return sorted(matched, key=lambda report: (report["date"], report["id"]), reverse=True)


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": report["id"],
        "report_id": report["id"],
        "patient_id": report["patient_id"],
        "type": report["type"],
        "date": report["date"],
        "clinician": report["clinician"],
    }


def get_report_by_id(report_id: str | None) -> dict[str, Any] | None:
    if not report_id:
        return None
    target = report_id.strip().upper()
    for report in reports():
        if report["id"].upper() == target:
            return report
    return None


def get_report(patient_id: str, report_type: str | None = None, which: str = "latest") -> dict[str, Any]:
    """Return the latest or oldest matching report, or the reports that do exist."""

    patient = get_patient(patient_id)
    if patient is None:
        return {"found": False, "reason": "unknown_patient", "patient_id": patient_id}
    canonical = canonical_report_type(report_type)
    available = list_reports(patient_id)
    typed = list_reports(patient_id, canonical) if canonical else available
    if not typed:
        return {
            "found": False,
            "reason": "missing_report",
            "patient": public_patient(patient),
            "requested_type": canonical,
            "available_reports": [report_summary(report) for report in available],
        }
    ordered = sorted(typed, key=lambda report: (report["date"], report["id"]))
    chosen = ordered[0] if which == "oldest" else ordered[-1]
    return {
        "found": True,
        "patient": public_patient(patient),
        "report": chosen,
        "which": "oldest" if which == "oldest" else "latest",
        "requested_type": canonical,
    }


def _keywords(question: str) -> list[str]:
    tokens = []
    for token in normalize(question).split():
        if token in _QUESTION_STOPWORDS or len(token) < 3:
            continue
        tokens.append(token)
    return tokens


def _report_chunks(report: dict[str, Any]) -> list[tuple[str, str]]:
    chunks = [("impression", report.get("impression") or "")]
    recommendations = report.get("recommendations") or []
    if isinstance(recommendations, list):
        chunks.append(("recommendations", " ".join(recommendations)))
    else:
        chunks.append(("recommendations", str(recommendations)))
    for finding in report.get("findings") or []:
        chunks.append(("findings", finding.get("description") or ""))
    return chunks


def _negated(text: str, keyword: str) -> bool:
    pattern = rf"\b(no|not|without|absent|negative for|free of|denies)\b(?:\W+\w+){{0,4}}\W+{re_escape(keyword)}\b"
    return bool(re_search(pattern, normalize(text)))


def re_escape(value: str) -> str:
    import re

    return re.escape(value)


def re_search(pattern: str, text: str) -> bool:
    import re

    return re.search(pattern, text) is not None


def answer_report_question(report_id: str, question: str) -> dict[str, Any]:
    """Answer only from one report. Anything else is not stated."""

    report = get_report_by_id(report_id)
    if report is None:
        return {"found": False, "reason": "unknown_report", "report_id": report_id}
    patient = get_patient(report["patient_id"])
    keywords = _keywords(question)
    chunks = _report_chunks(report)
    joined = " ".join(text for _, text in chunks)
    joined_norm = normalize(joined)
    supported = [keyword for keyword in keywords if term_supported(keyword, joined_norm)]
    if not keywords or len(supported) != len(keywords):
        return {
            "found": True,
            "stated": False,
            "answer": "Not stated in the report.",
            "report": report_summary(report),
            "patient": public_patient(patient) if patient else None,
            "quotes": [],
            "fields": [],
        }
    quotes: list[str] = []
    fields: list[str] = []
    negated = False
    for field, text in chunks:
        text_norm = normalize(text)
        if text and all(term_supported(keyword, text_norm) for keyword in keywords):
            quotes.append(text)
            fields.append(field)
            if any(_negated(text, keyword) for keyword in keywords):
                negated = True
    if not quotes:
        # The terms exist in the report, but not together in one sentence.
        for field, text in chunks:
            text_norm = normalize(text)
            if text and any(term_supported(keyword, text_norm) for keyword in keywords):
                quotes.append(text)
                fields.append(field)
                if any(_negated(text, keyword) for keyword in keywords):
                    negated = True
    quote = quotes[0]
    if negated:
        answer = f'No. The report states: "{quote}"'
    else:
        answer = f'Yes. The report states: "{quote}"'
    return {
        "found": True,
        "stated": True,
        "negated": negated,
        "answer": answer,
        "report": report_summary(report),
        "patient": public_patient(patient) if patient else None,
        "quotes": quotes,
        "fields": list(dict.fromkeys(fields)),
    }


def summarize_report(report_id: str) -> dict[str, Any]:
    """Build a short summary from the stored finding, impression, and recommendation text."""

    report = get_report_by_id(report_id)
    if report is None:
        return {"found": False, "reason": "unknown_report", "report_id": report_id}
    patient = get_patient(report["patient_id"])
    finding_text = "; ".join(
        finding.get("description") or "" for finding in report.get("findings") or [] if finding.get("description")
    )
    raw_recommendations = report.get("recommendations") or []
    if not isinstance(raw_recommendations, list):
        raw_recommendations = [str(raw_recommendations)]
    recommendation_text = "; ".join(
        item.strip().rstrip(".") for item in raw_recommendations if str(item).strip()
    )
    impression = str(report.get("impression") or "").strip().rstrip(".")
    name = patient["full_name"] if patient else report["patient_id"]
    summary = (
        f"{report['type']} report {report['id']} dated {report['date']} for {name}, "
        f"read by {report['clinician']}. Findings: {finding_text}. "
        f"Impression: {impression}. Recommendations: {recommendation_text}."
    )
    quotes = [finding.get("description") or "" for finding in report.get("findings") or []]
    quotes.append(report.get("impression") or "")
    return {
        "found": True,
        "summary": summary,
        "report": report,
        "report_id": report["id"],
        "patient": public_patient(patient) if patient else None,
        "quotes": [quote for quote in quotes if quote],
        "fields": ["findings", "impression", "recommendations"],
    }
