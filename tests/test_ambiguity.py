"""Similar names must be clarified, never guessed."""

import json


def test_priya_is_ambiguous_then_priya_shah_resolves(client):
    first = client.post(
        "/chat",
        json={"session_id": "ambig", "text": "Open Priya's latest OPG report"},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["needs_clarification"] is True
    assert body["data"] is None
    ids = [option["patient_id"] for option in body["clarification_options"]]
    assert ids == ["P001", "P002"]
    assert {option["full_name"] for option in body["clarification_options"]} == {
        "Priya Sharma",
        "Priya Shah",
    }
    assert all(option["dob_year"] for option in body["clarification_options"])
    assert all(option["last_visit"] for option in body["clarification_options"])
    blob = json.dumps(body)
    assert "R002" not in blob
    assert "R004" not in blob
    assert "Occlusal caries" not in blob

    second = client.post("/chat", json={"session_id": "ambig", "text": "Priya Shah"})
    assert second.status_code == 200
    resolved = second.json()
    assert resolved["needs_clarification"] is False
    assert resolved["data"]["report"]["patient_id"] == "P002"
    assert resolved["data"]["report"]["type"] == "OPG"
    assert resolved["data"]["report"]["id"] == "R004"
