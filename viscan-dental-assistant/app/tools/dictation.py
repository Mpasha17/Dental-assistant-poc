"""Turn a transcript into a grounded draft. The model may propose findings; Python keeps them."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.tools.patients import get_patient
from app.validation.grounding import ground_findings
from app.validation.teeth import apply_tooth_map

FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string"},
                    "anatomical_site": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "fdi_tooth": {"type": ["string", "null"]},
                            "universal_tooth": {"type": ["string", "null"]},
                            "quadrant": {"type": ["string", "null"]},
                            "jaw": {"type": ["string", "null"]},
                        },
                        "required": ["description"],
                    },
                    "classification": {"type": ["string", "null"]},
                    "certainty": {"type": "string", "enum": ["stated", "uncertain"]},
                    "evidence_span": {"type": "string"},
                },
                "required": ["finding", "anatomical_site", "certainty", "evidence_span"],
            },
        }
    },
    "required": ["findings"],
}

_DRAFT_FOOTER = "DRAFT - requires clinician review. Not a final diagnosis."
_drafts: dict[str, dict[str, Any]] = {}


def clear_drafts() -> None:
    _drafts.clear()


def get_draft(draft_id: str) -> dict[str, Any] | None:
    return _drafts.get(draft_id)


def build_dictation_prompt(transcript: str) -> str:
    return (
        "Extract explicit dental findings from the transcript.\n"
        "Rules: extract only what is explicitly said; copy the exact words as evidence_span; "
        "do not add diagnoses, treatment, or tooth numbers that are not derivable from the words. "
        "If the wording includes maybe, possibly, or looks like, set certainty to uncertain.\n\n"
        "TRANSCRIPT_START\n"
        f"{transcript}\n"
        "TRANSCRIPT_END\n"
    )


def render_draft_text(patient_name: str | None, findings: list[dict[str, Any]]) -> str:
    """Build the readable report from validated findings only."""

    lines = [
        "Clinical draft report",
        f"Patient: {patient_name or 'unassigned'}",
        "",
        "Findings:",
    ]
    if not findings:
        lines.append("- No supported findings were extracted from the transcript.")
    for index, finding in enumerate(findings, start=1):
        site = finding.get("anatomical_site") or {}
        location = site.get("description") or "unspecified site"
        extras = []
        if site.get("fdi_tooth"):
            extras.append(f"FDI {site['fdi_tooth']}")
        if site.get("universal_tooth"):
            extras.append(f"Universal {site['universal_tooth']}")
        suffix = f" ({', '.join(extras)})" if extras else ""
        classification = finding.get("classification") or "unspecified"
        lines.append(
            f"{index}. {location}{suffix}: {finding.get('finding')} "
            f"[classification: {classification}; certainty: {finding.get('certainty')}]"
        )
        lines.append(f'   Evidence: "{finding.get("evidence_span")}"')
    lines.extend(["", _DRAFT_FOOTER])
    return "\n".join(lines)


def _coerce_findings(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        findings = raw.get("findings", [])
        if isinstance(findings, list):
            return [item for item in findings if isinstance(item, dict)]
    return []


_CLASS_RULES = (
    (re.compile(r"\bhorizontally\b|\bhorizontal\b", re.IGNORECASE), "horizontal"),
    (re.compile(r"\bvertically\b|\bvertical\b", re.IGNORECASE), "vertical"),
    (re.compile(r"\bmesioangular", re.IGNORECASE), "mesioangular"),
    (re.compile(r"\bdistoangular", re.IGNORECASE), "distoangular"),
    (re.compile(r"\bcaries\b|\bcarious\b", re.IGNORECASE), "caries"),
    (re.compile(r"\bimpacted\b|\bimpaction\b", re.IGNORECASE), "impaction"),
)
_CLASS_CANON = {
    "horizontally": "horizontal",
    "horizontal": "horizontal",
    "vertically": "vertical",
    "vertical": "vertical",
    "mesioangularly": "mesioangular",
    "mesioangular": "mesioangular",
    "distoangularly": "distoangular",
    "distoangular": "distoangular",
    "carious": "caries",
    "caries": "caries",
    "impacted": "impaction",
    "impaction": "impaction",
}


def _classification_in(text: str) -> str | None:
    for pattern, label in _CLASS_RULES:
        if pattern.search(text):
            return label
    return None


def _infer_classification(finding: dict[str, Any], transcript: str) -> str | None:
    """Use the model's label when it named one, otherwise read the words."""

    raw = str(finding.get("classification") or "").strip()
    if raw:
        return _CLASS_CANON.get(raw.lower(), raw)
    site = finding.get("anatomical_site") or {}
    own_words = " ".join(
        str(part)
        for part in (finding.get("finding"), finding.get("evidence_span"), site.get("description"))
        if part
    )
    return _classification_in(own_words) or _classification_in(transcript)


def _normalize_finding(finding: dict[str, Any], transcript: str) -> dict[str, Any]:
    mapped = apply_tooth_map(finding)
    site = mapped.get("anatomical_site") or {}
    jaw = site.get("jaw")
    if jaw not in ("maxilla", "mandible"):
        site["jaw"] = None
    mapped["anatomical_site"] = site
    mapped["finding"] = str(mapped.get("finding") or "").strip()
    mapped["classification"] = _infer_classification(mapped, transcript)
    if mapped.get("certainty") not in ("stated", "uncertain"):
        mapped["certainty"] = "stated"
    mapped["evidence_span"] = str(mapped.get("evidence_span") or "")
    return mapped


def assemble_draft(
    transcript: str,
    raw: Any,
    patient_id: str | None = None,
) -> dict[str, Any]:
    """Ground model output, map teeth, and render the draft template."""

    kept, removed, warnings = ground_findings(transcript, _coerce_findings(raw))
    findings = [_normalize_finding(finding, transcript) for finding in kept]
    patient = get_patient(patient_id)
    if patient_id and patient is None:
        warnings.append("Unknown patient id. The draft was left unassigned.")
        patient_id = None
    draft = {
        "report_id": f"draft-{uuid4()}",
        "patient_id": patient["id"] if patient else None,
        "status": "draft",
        "requires_clinician_review": True,
        "findings": findings,
        "draft_text": render_draft_text(patient["full_name"] if patient else None, findings),
        "warnings": warnings,
        "unsupported_claims_removed": removed,
        "transcript": transcript,
    }
    _drafts[draft["report_id"]] = draft
    return draft


def create_draft(transcript: str, patient_id: str | None = None) -> tuple[dict[str, Any], str, bool]:
    """Ask the configured model for findings, then ground them.

    The third value is true when the hosted model failed and the rule parser ran.
    """

    from app.llm.router import get_llm_router

    router = get_llm_router()
    raw, provider_used = router.generate(build_dictation_prompt(transcript), FINDINGS_SCHEMA)
    draft = assemble_draft(transcript, raw, patient_id=patient_id)
    return draft, provider_used, bool(getattr(router, "used_fallback", False))


def update_draft(draft_id: str, findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Let a clinician edit findings. The text is rebuilt from the edited list.

    Edits that are not in the transcript are kept, because a person wrote them,
    and a warning is attached so the review state stays visible.
    """

    draft = _drafts.get(draft_id)
    if draft is None or draft.get("status") == "approved":
        return None
    transcript = draft["transcript"]
    kept, removed, warnings = ground_findings(transcript, findings)
    # Clinician text that failed grounding is preserved and flagged.
    failed_labels = set(removed)
    normalized = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        item = _normalize_finding(finding, transcript)
        label = str(finding.get("finding") or finding.get("evidence_span") or "")
        if label in failed_labels or not kept:
            item["certainty"] = item.get("certainty") or "uncertain"
        normalized.append(item)
    # Prefer the grounded certainty for findings that passed.
    grounded_by_span = {item.get("evidence_span"): item for item in kept}
    for item in normalized:
        grounded = grounded_by_span.get(item.get("evidence_span"))
        if grounded:
            item["certainty"] = grounded["certainty"]
    extra_warnings = [
        warning for warning in warnings if warning.startswith("Removed unsupported")
    ]
    rewritten = []
    for warning in extra_warnings:
        rewritten.append(warning.replace("Removed unsupported claim", "Edited finding is not fully grounded", 1))
    draft["findings"] = normalized
    draft["warnings"] = rewritten
    draft["unsupported_claims_removed"] = draft.get("unsupported_claims_removed") or []
    patient = get_patient(draft.get("patient_id"))
    draft["draft_text"] = render_draft_text(patient["full_name"] if patient else None, normalized)
    draft["status"] = "draft"
    draft["requires_clinician_review"] = True
    return draft


def approve_draft(draft_id: str, role: str) -> dict[str, Any] | None:
    """Mark a draft approved. The caller has already checked the role."""

    draft = _drafts.get(draft_id)
    if draft is None:
        return None
    draft["status"] = "approved"
    draft["requires_clinician_review"] = False
    draft["approved_by_role"] = role
    return draft
