"""Follow-ups reuse the open report and say so in sources."""


def test_summarize_his_report_uses_the_open_one(client):
    opened = client.post(
        "/chat",
        json={"session_id": "follow", "text": "Open Rahul's latest OPG report"},
    ).json()
    report_id = opened["data"]["report"]["id"]
    summary = client.post(
        "/chat",
        json={"session_id": "follow", "text": "Summarize his report"},
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body["needs_clarification"] is False
    assert body["data"]["report_id"] == report_id
    assert body["sources"][0]["report_id"] == report_id
    assert body["sources"][0]["patient_id"] == "P003"
    assert body["sources"][0]["quotes"]


def test_summarize_misheard_name_still_finds_rahul(client):
    body = client.post("/chat", json={"text": "Summarize Rahus Report"}).json()
    assert body["needs_clarification"] is False
    assert body["data"]["patient_id"] == "P003"
    assert body["data"]["report_id"] == "R008"


def test_summarize_without_context_asks(client):
    response = client.post("/chat", json={"text": "Summarize his report"})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_clarification"] is True
    assert body["data"] is None
    assert body["clarification_options"]


def test_question_not_stated_and_stated(client):
    client.post("/chat", json={"session_id": "q-rahul", "text": "Open Rahul's latest OPG report"})
    missing = client.post(
        "/chat",
        json={"session_id": "q-rahul", "text": "Does he have caries?"},
    ).json()
    assert "not stated in the report" in missing["answer"].lower()
    assert missing["sources"][0]["report_id"] == "R007"

    client.post("/chat", json={"session_id": "q-priya", "text": "Open Priya Sharma's latest OPG"})
    present = client.post(
        "/chat",
        json={"session_id": "q-priya", "text": "Does she have caries?"},
    ).json()
    assert present["needs_clarification"] is False
    assert "not stated in the report" not in present["answer"].lower()
    assert present["sources"][0]["report_id"] == "R002"
    assert present["sources"][0]["quotes"]
