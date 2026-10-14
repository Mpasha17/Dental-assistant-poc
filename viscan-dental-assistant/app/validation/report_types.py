"""Normalize spoken report and scan names to the four canonical types."""

from __future__ import annotations

import re

# Longer phrases first so "cone beam ct" wins over a shorter token.
_SYNONYMS: list[tuple[str, list[str]]] = [
    ("OPG", ["orthopantomogram", "panoramic", "pano", "opg"]),
    ("IOPA", ["periapical x-ray", "periapical xray", "periapical radiograph", "iopa"]),
    ("CBCT", ["cone beam ct", "cone-beam", "cone beam", "cbct"]),
    ("Bitewing", ["bite wing", "bite-wing", "bitewing"]),
]

_CANONICAL = {"opg": "OPG", "iopa": "IOPA", "cbct": "CBCT", "bitewing": "Bitewing"}


def canonical_report_type(value: str | None) -> str | None:
    """Map a type name or synonym to OPG, IOPA, CBCT, or Bitewing."""

    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    direct = _CANONICAL.get(cleaned.lower())
    if direct:
        return direct
    return detect_report_type(cleaned)


def detect_report_type(text: str) -> str | None:
    """Find a report type mentioned in a sentence.

    Bare "periapical" is intentionally not a type. In dictation it is a
    finding ("periapical radiolucency"), and the IOPA synonyms are the
    explicit phrases "periapical x-ray" and "IOPA".
    """

    lowered = text.lower()
    for canonical, phrases in _SYNONYMS:
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", lowered):
                return canonical
    return None
