"""Regression tests for config, provider retries, routing, grounding, and draft edits."""

from __future__ import annotations

import pytest

from app.llm.base import ToolCall


def test_default_groq_model(monkeypatch, tmp_path):
    from app import config

    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setattr(config, "load_dotenv_file", lambda: [])
    assert config.load_settings().groq_model == "openai/gpt-oss-120b"


def test_dotenv_groq_model_is_read_and_shadowing_is_reported(monkeypatch, tmp_path):
    from app.config import load_dotenv_file

    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_MODEL=openai/gpt-oss-120b\n", encoding="utf-8")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    assert load_dotenv_file(env_file) == []
    import os

    assert os.environ["GROQ_MODEL"] == "openai/gpt-oss-120b"
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    assert load_dotenv_file(env_file) == ["GROQ_MODEL"]


class _RateLimited(Exception):
    status_code = 429


def test_mistral_retries_429_with_backoff_then_raises():
    from app.llm.mistral import with_rate_limit_retry

    sleeps: list[float] = []
    calls = {"n": 0}

    def always_429():
        calls["n"] += 1
        raise _RateLimited("429 rate limit")

    with pytest.raises(_RateLimited):
        with_rate_limit_retry(always_429, sleep=sleeps.append)
    assert calls["n"] == 3
    assert sleeps == [1.5, 3.0]


def test_mistral_retry_recovers_and_ignores_other_errors():
    from app.llm.mistral import with_rate_limit_retry

    sleeps: list[float] = []
    attempts = iter([_RateLimited("429"), "ok"])

    def flaky():
        item = next(attempts)
        if isinstance(item, Exception):
            raise item
        return item

    assert with_rate_limit_retry(flaky, sleep=sleeps.append) == "ok"
    assert sleeps == [1.5]

    def broken():
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        with_rate_limit_retry(broken, sleep=sleeps.append)
    assert sleeps == [1.5]


def test_mistral_429_falls_back_to_rule_parser(monkeypatch):
    from app.llm import mistral
    from app.llm.router import ProviderRouter
    from app.llm.rule_based import RuleBasedProvider

    monkeypatch.setattr(mistral.time, "sleep", lambda _s: None)

    class Chat:
        def complete(self, **_kwargs):
            raise _RateLimited("429")

    class Client:
        chat = Chat()

    monkeypatch.setattr(mistral, "_client", lambda _key: Client())
    router = ProviderRouter(mistral.MistralProvider("k", "m"), RuleBasedProvider(), 0)
    call, provider = router.interpret("Open Rahul's latest OPG report", {}, [])
    assert provider == "rule"
    assert call.name == "get_report"


def test_summarize_her_report_overrides_list_reports(monkeypatch, client):
    opened = client.post(
        "/chat", json={"session_id": "s3", "text": "show me pryia sharma's opg"}
    ).json()
    report_id = opened["data"]["report"]["id"]
    assert opened["data"]["patient"]["id"] == "P001"

    class ListingRouter:
        used_fallback = False

        def interpret(self, text, context, tools):
            return ToolCall("list_reports", {"name": "Priya Sharma"}), "fake"

        def generate(self, prompt, schema):
            raise AssertionError("not used")

    monkeypatch.setattr("app.llm.router.get_llm_router", lambda: ListingRouter())
    body = client.post("/chat", json={"session_id": "s3", "text": "summarize her report"}).json()
    assert body["intent"] == "summarize_report"
    assert body["data"]["report_id"] == report_id


def test_prompt_steers_summary_away_from_list_reports():
    from app.llm.base import interpreter_messages

    system, _ = interpreter_messages("summarize her report", {"report_id": "R001"})
    assert "Never call list_reports for a summary request" in system


def test_hedge_anywhere_in_sentence_is_uncertain(client):
    response = client.post(
        "/dictation", json={"transcript": "there may be bone loss near the lower left first premolar"}
    )
    finding = response.json()["data"]["findings"][0]
    assert finding["certainty"] == "uncertain"
    assert finding["anatomical_site"]["fdi_tooth"] == "34"


@pytest.mark.parametrize(
    "transcript",
    [
        "Probably caries on the lower left first molar.",
        "Caries on the lower left first molar, cannot rule out pulp involvement.",
        "Caries on the lower left first molar?",
        "Lower left first molar caries, suspicious for early lesion.",
    ],
)
def test_hedge_words_in_evidence_sentence(transcript):
    from app.validation.grounding import certainty_for

    finding = {"evidence_span": "lower left first molar"}
    assert certainty_for(transcript, finding) == "uncertain"


def test_hedge_in_other_sentence_does_not_leak():
    from app.validation.grounding import certainty_for

    transcript = "Caries on the lower left first molar. The upper right canine may be rotated."
    assert certainty_for(transcript, {"evidence_span": "Caries on the lower left first molar"}) == "stated"


def test_filler_words_and_typo_resolve_to_p001(client):
    from app.llm.rule_based import extract_name

    assert extract_name("show me pryia sharma's opg").lower() == "pryia sharma"
    body = client.post("/chat", json={"text": "show me pryia sharma's opg"}).json()
    assert body["needs_clarification"] is False
    assert body["data"]["patient"]["id"] == "P001"


@pytest.mark.parametrize("phrase", ["Tooth 36 has deep distal caries", "#36 has deep distal caries"])
def test_bare_fdi_number_in_dictation(client, phrase):
    body = client.post("/dictation", json={"transcript": phrase}).json()
    findings = body["data"]["findings"]
    assert len(findings) == 1
    assert findings[0]["classification"] == "caries"
    assert findings[0]["certainty"] == "stated"
    assert findings[0]["anatomical_site"]["fdi_tooth"] == "36"


def test_invalid_fdi_number_is_not_a_tooth():
    from app.llm.rule_based import find_fdi

    assert find_fdi("tooth 19") is None
    assert find_fdi("tooth 50") is None
    assert find_fdi("#48") == "48"


def test_invalid_certainty_edit_returns_422(client):
    draft = client.post(
        "/dictation", json={"transcript": "Lower right third molar is horizontally impacted"}
    ).json()["data"]
    findings = draft["findings"]
    findings[0]["certainty"] = "probable"
    response = client.put(f"/draft/{draft['report_id']}", json={"findings": findings})
    assert response.status_code == 422
    assert "probable" in response.json()["detail"]
    assert "stated" in response.json()["detail"]


def test_draft_text_is_sentence_case(client):
    draft = client.post(
        "/dictation", json={"transcript": "Lower right third molar is horizontally impacted"}
    ).json()["data"]
    assert draft["draft_text"].startswith("Clinical draft report")


def test_ui_fixes_present():
    from app.config import STATIC_DIR

    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert "e.g. P003" in html
    assert "#draft-text { text-transform: none" in html
    assert "Available reports" in html
    assert "lastProvider" in html
