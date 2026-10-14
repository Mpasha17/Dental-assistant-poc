"""A missing study names what does exist."""


def test_kavya_has_no_opg(client):
    response = client.post("/chat", json={"text": "Open Kavya's latest OPG report"})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_clarification"] is False
    assert "no opg report found for kavya reddy" in body["answer"].lower()
    available = body["data"]["available_reports"]
    types = {item["type"] for item in available}
    assert "OPG" not in types
    assert {"IOPA", "Bitewing", "CBCT"} <= types
    assert body["data"]["report"] is None
    assert body["sources"]
