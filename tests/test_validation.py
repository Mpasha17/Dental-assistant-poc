"""Input limits, role checks, provider fallback, and log redaction."""

import json
import logging

from app.llm.router import ProviderRouter
from app.llm.rule_based import RuleBasedProvider
from app.logging_utils import PatientNameRedactionFilter


def test_oversized_text_is_rejected(client):
    response = client.post("/chat", json={"text": "a" * 2001})
    assert 400 <= response.status_code < 500


def test_bad_audio_type_is_rejected(client):
    response = client.post(
        "/voice",
        files={"audio": ("note.txt", b"hello", "text/plain")},
        data={"transcript": "Open Rahul's latest OPG report"},
    )
    assert 400 <= response.status_code < 500


def test_mock_voice_uses_transcript_field(client):
    response = client.post(
        "/voice",
        files={"audio": ("speech.webm", b"\x1a\x45\xdf\xa3fake", "audio/webm")},
        data={"transcript": "Open Rahul's latest OPG report", "session_id": "voice"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stt_provider"] == "mock"
    assert body["transcript"] == "Open Rahul's latest OPG report"
    assert body["data"]["report"]["id"] == "R007"


def test_assistant_cannot_approve_draft(client):
    drafted = client.post(
        "/dictation",
        json={"transcript": "Lower right third molar is horizontally impacted"},
    ).json()
    draft_id = drafted["data"]["report_id"]
    denied = client.post(f"/draft/{draft_id}/approve", headers={"X-User-Role": "assistant"})
    assert denied.status_code == 403
    still = client.get(f"/reports/{draft_id}").json()["report"]
    assert still["status"] == "draft"
    approved = client.post(f"/draft/{draft_id}/approve", headers={"X-User-Role": "dentist"})
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["requires_clinician_review"] is False


def test_provider_fallback(monkeypatch, client):
    class Boom:
        name = "gemini"

        def interpret(self, *_args, **_kwargs):
            raise RuntimeError("429 rate limit")

        def generate(self, *_args, **_kwargs):
            raise RuntimeError("429 rate limit")

    monkeypatch.setattr(
        "app.llm.router.get_llm_router",
        lambda: ProviderRouter(Boom(), RuleBasedProvider(), timeout_s=2),
    )
    body = client.post("/chat", json={"text": "Open Rahul's latest OPG report"}).json()
    assert body["provider_used"] == "rule"
    assert body["data"]["report"]["id"] == "R007"
    assert any("rule interpreter" in warning for warning in body["warnings"])


def test_health_reports_key_presence_not_the_key(monkeypatch, client):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    from app.config import reset_settings

    reset_settings()
    body = client.get("/health").json()
    assert body["keys"]["gemini"] is True
    assert "super-secret-value" not in json.dumps(body)
    assert "llm_provider" in body
    assert "stt_provider" in body


def test_logs_redact_patient_names():
    record = logging.LogRecord(
        name="viscan",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="resolved Priya Sharma but logging P001 only",
        args=(),
        exc_info=None,
    )
    assert PatientNameRedactionFilter().filter(record) is True
    message = record.getMessage()
    assert "Priya Sharma" not in message
    assert "P001" in message


def test_optional_sdks_stay_unimported():
    import sys

    assert "groq" not in sys.modules
    assert "mistralai" not in sys.modules
    assert "google.genai" not in sys.modules
    assert "faster_whisper" not in sys.modules
