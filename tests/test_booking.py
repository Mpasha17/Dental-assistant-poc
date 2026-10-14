"""A slot is booked only after an explicit confirmation, and only once."""

from app.tools.booking import book_slot
from app.tools.store import slots


def _slot(slot_id: str) -> dict:
    return next(slot for slot in slots() if slot["id"] == slot_id)


def test_booking_waits_for_confirmation(client):
    proposed = client.post(
        "/chat",
        json={"session_id": "book", "text": "Book an OPG for Rahul tomorrow morning"},
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["intent"] == "propose_booking"
    assert body["data"]["booked"] is False
    assert body["data"]["proposed_slot"]["id"] == "S001"
    assert _slot("S001")["booked"] is False

    confirmed = client.post("/chat", json={"session_id": "book", "text": "yes, confirm"})
    assert confirmed.status_code == 200
    done = confirmed.json()
    assert done["data"]["booked"] is True
    assert done["data"]["slot"]["id"] == "S001"
    assert done["data"]["slot"]["patient_id"] == "P003"
    assert _slot("S001")["booked"] is True


def test_booked_slot_cannot_be_double_booked(client):
    client.post(
        "/chat",
        json={"session_id": "book2", "text": "Book an OPG for Rahul tomorrow morning"},
    )
    client.post("/chat", json={"session_id": "book2", "text": "yes, confirm"})
    again = book_slot("S001", "P004", confirmed=True)
    assert again["booked"] is False
    assert again["reason"] == "already_booked"
    assert _slot("S001")["patient_id"] == "P003"

    prebooked = book_slot("S002", "P003", confirmed=True)
    assert prebooked["booked"] is False
    assert prebooked["reason"] == "already_booked"

    via_chat = client.post(
        "/chat",
        json={"session_id": "book3", "text": "Book slot S002 for Ananya Iyer"},
    ).json()
    assert via_chat["data"]["booked"] is False
    assert "already booked" in via_chat["answer"].lower()


def test_model_date_is_replaced_by_the_demo_clock(monkeypatch, client):
    from app.llm.base import ToolCall

    class WrongDateRouter:
        used_fallback = False

        def interpret(self, text, context, tools):
            return ToolCall(
                "check_slots",
                {
                    "scan_type": "OPG",
                    "date_from": "2030-01-01",
                    "date_to": "2030-01-01",
                    "part_of_day": "evening",
                    "patient_id": "P001",
                },
            ), "wrong-date"

        def generate(self, prompt, schema):
            raise AssertionError("not used")

    monkeypatch.setattr("app.llm.router.get_llm_router", lambda: WrongDateRouter())
    body = client.post(
        "/chat",
        json={"text": "Book an OPG for Rahul tomorrow morning"},
    ).json()
    assert body["intent"] == "propose_booking"
    assert body["data"]["booked"] is False
    assert body["data"]["proposed_slot"]["id"] == "S001"
    assert body["data"]["patient_id"] == "P003"


def test_model_cannot_skip_confirmation(monkeypatch, client):
    from app.llm.base import ToolCall

    class SneakyRouter:
        used_fallback = False

        def interpret(self, text, context, tools):
            return ToolCall("book_slot", {"slot_id": "S001", "patient_id": "P003", "confirmed": True}), "sneaky"

        def generate(self, prompt, schema):
            raise AssertionError("not used")

    monkeypatch.setattr("app.llm.router.get_llm_router", lambda: SneakyRouter())
    body = client.post(
        "/chat",
        json={"text": "Book an OPG for Rahul tomorrow morning"},
    ).json()
    assert body["data"]["booked"] is False
    assert _slot("S001")["booked"] is False
