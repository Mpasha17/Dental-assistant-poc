"""Deterministic tooth-number mapping from plain-language sites.

FDI and Universal numbers are filled in Python. A model-supplied number is
kept only when the words do not name a tooth and the digits themselves are
the site.
"""

from __future__ import annotations

import re
from typing import Any

# More specific names come first so "first molar" is not read as "molar".
_TOOTH_TYPES: list[tuple[str, int | None]] = [
    ("third molar", 8),
    ("3rd molar", 8),
    ("wisdom tooth", 8),
    ("wisdom", 8),
    ("second molar", 7),
    ("2nd molar", 7),
    ("first molar", 6),
    ("1st molar", 6),
    ("second premolar", 5),
    ("2nd premolar", 5),
    ("second bicuspid", 5),
    ("first premolar", 4),
    ("1st premolar", 4),
    ("first bicuspid", 4),
    ("lateral incisor", 2),
    ("central incisor", 1),
    ("canine", 3),
    ("cuspid", 3),
    ("premolar", None),
    ("molar", None),
    ("incisor", None),
]

_QUADRANTS = {
    ("maxilla", "right"): 1,
    ("maxilla", "left"): 2,
    ("mandible", "left"): 3,
    ("mandible", "right"): 4,
}

_QUADRANT_NAME = {1: "upper right", 2: "upper left", 3: "lower left", 4: "lower right"}
_JAW = {1: "maxilla", 2: "maxilla", 3: "mandible", 4: "mandible"}


def fdi_to_universal(fdi: str) -> str | None:
    """Convert a permanent FDI tooth number to Universal numbering."""

    if not re.fullmatch(r"[1-4][1-8]", fdi):
        return None
    quadrant = int(fdi[0])
    position = int(fdi[1])
    if quadrant == 1:
        return str(9 - position)
    if quadrant == 2:
        return str(8 + position)
    if quadrant == 3:
        return str(25 - position)
    return str(24 + position)


def _jaw_and_side(text: str) -> tuple[str | None, str | None]:
    jaw = None
    side = None
    if re.search(r"\b(lower|mandibular|mandible)\b", text):
        jaw = "mandible"
    elif re.search(r"\b(upper|maxillary|maxilla)\b", text):
        jaw = "maxilla"
    if re.search(r"\bleft\b", text):
        side = "left"
    elif re.search(r"\bright\b", text):
        side = "right"
    return jaw, side


def _position(text: str) -> int | None:
    for phrase, position in _TOOTH_TYPES:
        if position is None:
            continue
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return position
    return None


def _explicit_fdi(text: str) -> str | None:
    labeled = re.search(r"\b(?:fdi|tooth)\s*([1-4][1-8])\b", text)
    if labeled:
        return labeled.group(1)
    bare = re.search(r"\b([1-4][1-8])\b", text)
    if bare:
        return bare.group(1)
    return None


def map_anatomy(description: str) -> dict[str, str | None]:
    """Return jaw, quadrant, FDI, and Universal fields derived from a site description."""

    text = (description or "").lower()
    jaw, side = _jaw_and_side(text)
    position = _position(text)
    fdi: str | None = None
    if jaw and side and position:
        quadrant_number = _QUADRANTS[(jaw, side)]
        fdi = f"{quadrant_number}{position}"
    elif (explicit := _explicit_fdi(text)):
        fdi = explicit
        quadrant_number = int(fdi[0])
        jaw = _JAW[quadrant_number]
        side = "right" if quadrant_number in (1, 4) else "left"
    quadrant = None
    if fdi:
        quadrant = _QUADRANT_NAME[int(fdi[0])]
        jaw = _JAW[int(fdi[0])]
    elif jaw and side:
        quadrant = f"{'upper' if jaw == 'maxilla' else 'lower'} {side}"
    return {
        "jaw": jaw,
        "quadrant": quadrant,
        "fdi_tooth": fdi,
        "universal_tooth": fdi_to_universal(fdi) if fdi else None,
    }


def apply_tooth_map(finding: dict[str, Any]) -> dict[str, Any]:
    """Fill anatomical numbers from the site description, ignoring invented ones."""

    updated = dict(finding)
    site = dict(updated.get("anatomical_site") or {})
    description = str(site.get("description") or updated.get("finding") or "")
    mapped = map_anatomy(description)
    if not mapped["fdi_tooth"]:
        mapped = map_anatomy(str(updated.get("finding") or ""))
    site["description"] = site.get("description") or description
    site["jaw"] = mapped["jaw"]
    site["quadrant"] = mapped["quadrant"]
    site["fdi_tooth"] = mapped["fdi_tooth"]
    site["universal_tooth"] = mapped["universal_tooth"]
    updated["anatomical_site"] = site
    return updated
