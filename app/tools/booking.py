"""Scan slots. Booking changes state only when confirmed is true."""

from __future__ import annotations

from typing import Any

from app.tools.store import slots
from app.validation.report_types import canonical_report_type


def get_slot(slot_id: str | None) -> dict[str, Any] | None:
    if not slot_id:
        return None
    target = slot_id.strip().upper()
    for slot in slots():
        if slot["id"].upper() == target:
            return slot
    return None


def check_slots(
    scan_type: str | None,
    date_from: str | None = None,
    date_to: str | None = None,
    part_of_day: str | None = None,
) -> list[dict[str, Any]]:
    """Return matching slots, including ones that are already booked."""

    canonical = canonical_report_type(scan_type) if scan_type else None
    part = (part_of_day or "").strip().lower() or None
    matched: list[dict[str, Any]] = []
    for slot in slots():
        if canonical and slot["scan_type"] != canonical:
            continue
        if date_from and slot["date"] < date_from:
            continue
        if date_to and slot["date"] > date_to:
            continue
        if part and slot["part_of_day"] != part:
            continue
        matched.append(slot)
    matched.sort(key=lambda slot: (slot["date"], slot["time"], slot["id"]))
    return matched


def book_slot(slot_id: str, patient_id: str, confirmed: bool = False) -> dict[str, Any]:
    """Book a free slot. A second booking of the same slot is refused."""

    slot = get_slot(slot_id)
    if slot is None:
        return {"booked": False, "reason": "unknown_slot", "slot_id": slot_id, "patient_id": patient_id}
    if not confirmed:
        return {
            "booked": False,
            "reason": "confirmation_required",
            "slot": slot,
            "slot_id": slot["id"],
            "patient_id": patient_id,
        }
    if slot["booked"]:
        return {
            "booked": False,
            "reason": "already_booked",
            "slot": slot,
            "slot_id": slot["id"],
            "patient_id": slot.get("patient_id"),
        }
    slot["booked"] = True
    slot["patient_id"] = patient_id
    return {"booked": True, "reason": "booked", "slot": slot, "slot_id": slot["id"], "patient_id": patient_id}
