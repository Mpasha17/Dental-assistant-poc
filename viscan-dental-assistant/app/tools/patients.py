"""Patient lookup. Name resolution always happens here, never inside the model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from app.tools.store import patients

_MATCH_THRESHOLD = 85
_AMBIGUITY_GAP = 10


def normalize_name(value: str) -> str:
    text = (value or "").lower().replace("'", "").replace("'", "")
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def public_patient(patient: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patient["id"],
        "patient_id": patient["id"],
        "full_name": patient["full_name"],
        "first_name": patient["first_name"],
        "last_name": patient["last_name"],
        "sex": patient["sex"],
        "dob": patient["dob"],
        "dob_year": patient["dob_year"],
        "pronoun": patient["pronoun"],
        "last_visit": patient["last_visit"],
    }


def clarification_option(patient: dict[str, Any]) -> dict[str, Any]:
    return {
        "patient_id": patient["id"],
        "full_name": patient["full_name"],
        "dob_year": patient["dob_year"],
        "last_visit": patient["last_visit"],
    }


def get_patient(patient_id: str | None) -> dict[str, Any] | None:
    if not patient_id:
        return None
    target = patient_id.strip().upper()
    for patient in patients():
        if patient["id"].upper() == target:
            return patient
    return None


@dataclass
class ResolveResult:
    """`unique`, `ambiguous`, or `none`."""

    status: str
    patients: list[dict[str, Any]]

    @property
    def patient(self) -> dict[str, Any] | None:
        if self.status == "unique":
            return self.patients[0]
        return None


def resolve_patient(name: str) -> ResolveResult:
    """Resolve a spoken name.

    Precedence is exact full name, then a unique first name, then fuzzy
    full-name match at score >= 85. A single token such as "Rahus" can also
    match one first name at partial score >= 85. Two candidates within 10
    points of the best score are ambiguous and must be asked about.
    """

    roster = patients()
    compact = re.sub(r"[^A-Za-z0-9]", "", name or "").upper()
    if re.fullmatch(r"P\d{3}", compact):
        matched = [patient for patient in roster if patient["id"] == compact]
        if len(matched) == 1:
            return ResolveResult("unique", matched)

    query = normalize_name(name)
    if not query:
        return ResolveResult("none", [])

    exact = [patient for patient in roster if normalize_name(patient["full_name"]) == query]
    if len(exact) == 1:
        return ResolveResult("unique", exact)
    if len(exact) > 1:
        return ResolveResult("ambiguous", exact)

    first = [patient for patient in roster if normalize_name(patient["first_name"]) == query]
    if len(first) == 1:
        return ResolveResult("unique", first)
    if len(first) > 1:
        return ResolveResult("ambiguous", sorted(first, key=lambda item: item["id"]))

    last = [patient for patient in roster if normalize_name(patient["last_name"]) == query]
    if len(last) == 1:
        return ResolveResult("unique", last)
    if len(last) > 1:
        return ResolveResult("ambiguous", sorted(last, key=lambda item: item["id"]))

    scored: list[tuple[float, dict[str, Any]]] = []
    for patient in roster:
        full = normalize_name(patient["full_name"])
        score = float(fuzz.token_sort_ratio(query, full))
        if score >= _MATCH_THRESHOLD:
            scored.append((score, patient))
    if not scored and " " not in query and len(query) >= 4:
        for patient in roster:
            score = float(fuzz.partial_ratio(query, normalize_name(patient["first_name"])))
            if score >= _MATCH_THRESHOLD:
                scored.append((score, patient))
    if not scored:
        return ResolveResult("none", [])
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    top = scored[0][0]
    close = [patient for score, patient in scored if top - score <= _AMBIGUITY_GAP]
    if len(close) >= 2:
        return ResolveResult("ambiguous", close)
    return ResolveResult("unique", [scored[0][1]])


def select_candidate(text: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick one of the people already offered in a clarification question."""

    raw = text.strip().lower()
    query = normalize_name(text)
    for patient in candidates:
        if raw == patient["id"].lower():
            return patient
    exact = [patient for patient in candidates if normalize_name(patient["full_name"]) == query]
    if len(exact) == 1:
        return exact[0]
    if re.fullmatch(r"(19|20)\d{2}", query):
        year_hits = [patient for patient in candidates if str(patient["dob_year"]) == query]
        if len(year_hits) == 1:
            return year_hits[0]
    first = [patient for patient in candidates if normalize_name(patient["first_name"]) == query]
    if len(first) == 1:
        return first[0]
    last = [patient for patient in candidates if normalize_name(patient["last_name"]) == query]
    if len(last) == 1:
        return last[0]
    ordinals = {
        "1": 0,
        "first": 0,
        "first one": 0,
        "the first": 0,
        "the first one": 0,
        "2": 1,
        "second": 1,
        "second one": 1,
        "the second": 1,
        "the second one": 1,
    }
    if raw in ordinals and ordinals[raw] < len(candidates):
        return candidates[ordinals[raw]]
    return None


def all_options() -> list[dict[str, Any]]:
    return [clarification_option(patient) for patient in patients()]
