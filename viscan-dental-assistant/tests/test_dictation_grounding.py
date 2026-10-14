"""Dictation keeps only findings the transcript supports."""


def _draft(client, transcript: str) -> dict:
    response = client.post("/dictation", json={"transcript": transcript})
    assert response.status_code == 200
    body = response.json()
    assert body["requires_clinician_review"] is True
    assert body["data"]["status"] == "draft"
    assert body["data"]["requires_clinician_review"] is True
    assert "DRAFT - requires clinician review. Not a final diagnosis." in body["data"]["draft_text"]
    return body


def test_horizontal_impaction_maps_fdi_48(client):
    body = _draft(client, "Lower right third molar is horizontally impacted")
    findings = body["data"]["findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["anatomical_site"]["fdi_tooth"] == "48"
    assert finding["anatomical_site"]["universal_tooth"] == "32"
    assert finding["anatomical_site"]["jaw"] == "mandible"
    assert finding["classification"] == "horizontal"
    assert finding["certainty"] == "stated"
    assert finding["evidence_span"] in body["data"]["transcript"]
    assert body["data"]["unsupported_claims_removed"] == []


def test_possible_caries_is_uncertain(client):
    body = _draft(client, "Possibly caries on the upper left first molar")
    findings = body["data"]["findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["certainty"] == "uncertain"
    assert finding["anatomical_site"]["fdi_tooth"] == "26"
    assert finding["classification"] == "caries"


def test_blank_classification_is_read_from_the_words(monkeypatch, client):
    class BareRouter:
        used_fallback = False

        def generate(self, prompt, schema):
            return {
                "findings": [
                    {
                        "finding": "Lower right third molar is impacted",
                        "anatomical_site": {"description": "lower right third molar"},
                        "classification": None,
                        "certainty": "stated",
                        "evidence_span": "Lower right third molar is horizontally impacted",
                    }
                ]
            }, "bare"

        def interpret(self, *_args, **_kwargs):
            raise AssertionError("dictation should not interpret")

    monkeypatch.setattr("app.llm.router.get_llm_router", lambda: BareRouter())
    body = _draft(client, "Lower right third molar is horizontally impacted")
    assert body["data"]["findings"][0]["classification"] == "horizontal"


def test_invented_finding_is_removed(monkeypatch, client):
    class FakeRouter:
        used_fallback = False

        def generate(self, prompt, schema):
            return (
                {
                    "findings": [
                        {
                            "finding": "Lower right third molar is horizontally impacted",
                            "anatomical_site": {"description": "lower right third molar"},
                            "classification": "horizontal",
                            "certainty": "stated",
                            "evidence_span": "Lower right third molar is horizontally impacted",
                        },
                        {
                            "finding": "periapical abscess on 36",
                            "anatomical_site": {"description": "tooth 36", "fdi_tooth": "36"},
                            "classification": "periapical abscess",
                            "certainty": "stated",
                            "evidence_span": "periapical abscess on 36",
                        },
                    ]
                },
                "fake",
            )

        def interpret(self, *_args, **_kwargs):
            raise AssertionError("dictation should not interpret")

    monkeypatch.setattr("app.llm.router.get_llm_router", lambda: FakeRouter())
    body = _draft(client, "Lower right third molar is horizontally impacted")
    assert len(body["data"]["findings"]) == 1
    assert body["data"]["findings"][0]["anatomical_site"]["fdi_tooth"] == "48"
    removed = " ".join(body["data"]["unsupported_claims_removed"]).lower()
    assert "periapical abscess on 36" in removed
    assert "abscess" not in body["data"]["draft_text"].lower()
