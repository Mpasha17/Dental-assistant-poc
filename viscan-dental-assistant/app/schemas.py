"""Pydantic models for the HTTP API and tool arguments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["dentist", "radiologist", "assistant"]
Certainty = Literal["stated", "uncertain"]
Jaw = Literal["maxilla", "mandible"]
WhichReport = Literal["latest", "oldest"]
PartOfDay = Literal["morning", "afternoon", "evening"]


class ChatRequest(BaseModel):
    session_id: str | None = None
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text is empty")
        return value.strip()


class DictationRequest(BaseModel):
    session_id: str | None = None
    patient_id: str | None = None
    transcript: str = Field(min_length=1, max_length=2000)

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("transcript is empty")
        return value.strip()


class DraftUpdateRequest(BaseModel):
    findings: list[dict[str, Any]] = Field(min_length=0)


class Source(BaseModel):
    report_id: str | None = None
    patient_id: str | None = None
    fields: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)


class ClarificationOption(BaseModel):
    patient_id: str
    full_name: str
    dob_year: int
    last_visit: str | None = None


class UnifiedResponse(BaseModel):
    """One shape for chat, voice, and dictation."""

    session_id: str
    intent: str
    answer: str
    data: Any = None
    sources: list[Source] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_options: list[ClarificationOption] = Field(default_factory=list)
    requires_clinician_review: bool = False
    provider_used: str
    stt_provider: str | None = None
    transcript: str | None = None
    latency_ms: int = 0
    warnings: list[str] = Field(default_factory=list)


class AnatomicalSite(BaseModel):
    description: str
    fdi_tooth: str | None = None
    universal_tooth: str | None = None
    quadrant: str | None = None
    jaw: Jaw | None = None


class Finding(BaseModel):
    finding: str
    anatomical_site: AnatomicalSite
    classification: str | None = None
    certainty: Certainty
    evidence_span: str


class DraftReport(BaseModel):
    report_id: str
    patient_id: str | None = None
    status: Literal["draft", "approved"]
    requires_clinician_review: bool
    findings: list[Finding]
    draft_text: str
    warnings: list[str] = Field(default_factory=list)
    unsupported_claims_removed: list[str] = Field(default_factory=list)
    transcript: str


class FindPatientArgs(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ListReportsArgs(BaseModel):
    patient_id: str | None = None
    name: str | None = None
    report_type: str | None = None


class GetReportArgs(BaseModel):
    patient_id: str | None = None
    name: str | None = None
    report_type: str | None = None
    which: str = "latest"


class SummarizeReportArgs(BaseModel):
    report_id: str | None = None
    pronoun: str | None = None


class AnswerQuestionArgs(BaseModel):
    report_id: str | None = None
    question: str = Field(min_length=1)
    pronoun: str | None = None


class DraftArgs(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)
    patient_id: str | None = None
    name: str | None = None


class CheckSlotsArgs(BaseModel):
    scan_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    part_of_day: str | None = None
    name: str | None = None
    patient_id: str | None = None
    slot_id: str | None = None


class BookSlotArgs(BaseModel):
    slot_id: str
    patient_id: str
    confirmed: bool = False


TOOL_ARG_MODELS = {
    "find_patient": FindPatientArgs,
    "list_reports": ListReportsArgs,
    "get_report": GetReportArgs,
    "summarize_report": SummarizeReportArgs,
    "answer_report_question": AnswerQuestionArgs,
    "draft_clinical_report": DraftArgs,
    "check_slots": CheckSlotsArgs,
    "book_slot": BookSlotArgs,
}
