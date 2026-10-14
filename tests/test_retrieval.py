"""Report retrieval chooses the newest matching study."""


def test_rahul_latest_opg(client):
    response = client.post("/chat", json={"text": "Open Rahul's latest OPG report"})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_clarification"] is False
    assert body["provider_used"] == "rule"
    assert body["data"]["report"]["id"] == "R007"
    assert body["data"]["report"]["patient_id"] == "P003"
    assert body["data"]["report"]["type"] == "OPG"
    assert body["data"]["report"]["date"] == "2026-08-19"
    assert body["sources"][0]["report_id"] == "R007"
    assert body["sources"][0]["patient_id"] == "P003"
    assert body["sources"][0]["quotes"]


def test_priya_sharma_newer_of_two_opgs(client):
    response = client.post("/chat", json={"text": "Open Priya Sharma's latest OPG"})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_clarification"] is False
    report = body["data"]["report"]
    assert report["patient_id"] == "P001"
    assert report["type"] == "OPG"
    assert report["id"] == "R002"
    assert report["date"] == "2026-09-20"
    assert body["sources"][0]["report_id"] == "R002"
