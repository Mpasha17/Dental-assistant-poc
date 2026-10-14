"""Load mutable in-memory copies of the synthetic fixtures."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.config import DATA_DIR

_patients: list[dict[str, Any]] = []
_reports: list[dict[str, Any]] = []
_slots: list[dict[str, Any]] = []
_vocab: dict[str, Any] = {}
_loaded = False


def _read(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def reset_stores() -> None:
    """Reload fixtures from disk so tests do not leak bookings or edits."""

    global _patients, _reports, _slots, _vocab, _loaded
    _patients = deepcopy(_read("patients.json"))
    _reports = deepcopy(_read("reports.json"))
    _slots = deepcopy(_read("slots.json"))
    _vocab = deepcopy(_read("dental_vocab.json"))
    _loaded = True


def _ensure() -> None:
    if not _loaded:
        reset_stores()


def patients() -> list[dict[str, Any]]:
    _ensure()
    return _patients


def reports() -> list[dict[str, Any]]:
    _ensure()
    return _reports


def slots() -> list[dict[str, Any]]:
    _ensure()
    return _slots


def vocab() -> dict[str, Any]:
    _ensure()
    return _vocab
