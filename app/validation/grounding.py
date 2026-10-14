"""Drop clinical claims that the transcript does not actually say."""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "of", "on", "in", "at", "to",
    "for", "and", "or", "with", "this", "that", "there", "be", "been", "being",
    "it", "its", "by", "from", "as", "tooth", "teeth", "region", "area", "side",
    "has", "have", "had", "shows", "show", "seen", "noted", "present", "patient",
    "report", "into", "than", "then", "over", "under", "also", "very", "just",
}

_SYNONYM_GROUPS = [
    {"horizontal", "horizontally"},
    {"vertical", "vertically"},
    {"impacted", "impaction", "impactions"},
    {"caries", "carious", "decay", "cavity", "cavities"},
    {"mesioangular", "mesioangularly"},
    {"distoangular", "distoangularly"},
    {"periapical"},
    {"abscess", "abscesses"},
    {"molar", "molars"},
    {"premolar", "premolars", "bicuspid", "bicuspids"},
    {"lower", "mandibular", "mandible"},
    {"upper", "maxillary", "maxilla"},
    {"third", "3rd"},
    {"first", "1st"},
    {"second", "2nd"},
    {"canine", "cuspid", "cuspids"},
    {"incisor", "incisors"},
    {"wisdom"},
    {"left"},
    {"right"},
    {"unerupted"},
    {"radiolucency", "radiolucent", "radiolucencies"},
    {"restoration", "restored", "filling", "fillings"},
    {"fracture", "fractured"},
    {"missing", "absent"},
    {"bone"},
    {"loss"},
    {"calculus"},
    {"periodontal"},
    {"enamel"},
    {"dentine", "dentin"},
    {"pulp"},
    {"crown"},
    {"root", "roots"},
    {"canal"},
    {"lesion", "lesions"},
    {"supernumerary"},
    {"erupted"},
    {"intact"},
    {"occlusal"},
    {"interproximal"},
    {"mild"},
    {"moderate"},
    {"generalized"},
    {"unchanged"},
    {"early"},
    {"possible", "possibly"},
    {"maybe"},
    {"anterior"},
    {"posterior"},
    {"apex", "apical"},
    {"distal"},
    {"mesial"},
    {"dense"},
    {"healed"},
    {"socket"},
    {"sinus"},
    {"mucosal"},
    {"thickening"},
    {"implant"},
    {"height"},
    {"adequate"},
    {"close"},
    {"inferior"},
    {"alveolar"},
    {"nerve"},
    {"completed"},
    {"widening"},
    {"palatal"},
    {"nasal"},
    {"floor"},
    {"central"},
    {"confined"},
    {"uncomplicated"},
    {"exposed"},
    {"margins"},
    {"separate"},
    {"not"},
]

_SYNONYMS: dict[str, set[str]] = {}
for group in _SYNONYM_GROUPS:
    for token in group:
        _SYNONYMS[token] = group

_HEDGES = (
    "may",
    "maybe",
    "probably",
    "probable",
    "likely",
    "suspicious for",
    "cannot rule out",
    "cant rule out",
    "query",
    "possibly",
    "possible",
    "looks like",
    "looks to be",
    "appears to",
    "apparently",
    "might",
    "could be",
    "suspect",
    "suspected",
    "uncertain",
    "questionable",
    "suggestive of",
    "i think",
    "not sure",
)


def normalize(text: str) -> str:
    """Lowercase and strip punctuation so span checks ignore trivial differences."""

    value = (text or "").lower().replace("'", "").replace("'", "").replace("`", "")
    value = value.replace("mesio-angular", "mesioangular").replace("disto-angular", "distoangular")
    value = value.replace("peri-apical", "periapical")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: str) -> list[str]:
    return [token for token in normalize(text).split() if token and token not in _STOPWORDS and len(token) > 1]


def term_supported(term: str, transcript_norm: str) -> bool:
    """A term is supported when it, or an allowed synonym, is in the transcript."""

    if term.isdigit():
        return bool(re.search(rf"\b{re.escape(term)}\b", transcript_norm))
    options = _SYNONYMS.get(term, {term})
    return any(re.search(rf"\b{re.escape(option)}\b", transcript_norm) for option in options)


def span_in_transcript(span: str, transcript: str) -> bool:
    """Evidence must be a normalized substring, or a close fuzzy match when long enough."""

    span_norm = normalize(span)
    transcript_norm = normalize(transcript)
    if not span_norm:
        return False
    if span_norm in transcript_norm:
        return True
    if len(span_norm) < 12:
        return False
    return fuzz.partial_ratio(span_norm, transcript_norm) >= 90


def _claim_texts(finding: dict[str, Any]) -> list[str]:
    site = finding.get("anatomical_site") or {}
    return [
        str(finding.get("finding") or ""),
        str(finding.get("classification") or ""),
        str(site.get("description") or ""),
    ]


def finding_supported(finding: dict[str, Any], transcript: str) -> tuple[bool, str]:
    """Return whether every key term in the finding is backed by the transcript."""

    span = str(finding.get("evidence_span") or "")
    if not span_in_transcript(span, transcript):
        return False, "evidence span is not in the transcript"
    transcript_norm = normalize(transcript)
    missing: list[str] = []
    seen: set[str] = set()
    for text in _claim_texts(finding):
        for token in _tokens(text):
            if token in seen:
                continue
            seen.add(token)
            if not term_supported(token, transcript_norm):
                missing.append(token)
    if missing:
        return False, "unsupported terms: " + ", ".join(missing)
    return True, ""


def hedge_in(text: str) -> bool:
    blob = normalize(text)
    for hedge in _HEDGES:
        cleaned = normalize(hedge)
        if " " in cleaned:
            if cleaned in blob:
                return True
        elif re.search(rf"\b{re.escape(cleaned)}\b", blob):
            return True
    return False


def _sentences(transcript: str) -> list[tuple[int, int, str]]:
    """Sentence slices of the transcript with their character offsets.

    The terminator stays with its sentence, so "caries?" still reads as a hedge.
    """

    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r"[.!?;\n]+", transcript):
        end = match.end()
        if transcript[start:end].strip():
            spans.append((start, end, transcript[start:end]))
        start = end
    if transcript[start:].strip():
        spans.append((start, len(transcript), transcript[start:]))
    return spans


def sentence_for_span(transcript: str, span: str) -> str:
    """The transcript sentence(s) that contain the evidence span."""

    if not span:
        return transcript
    index = transcript.lower().find(span.lower())
    if index < 0:
        span_norm = normalize(span)
        for _, _, sentence in _sentences(transcript):
            if span_norm and span_norm in normalize(sentence):
                return sentence
        return span
    end = index + len(span)
    covering = [text for start, stop, text in _sentences(transcript) if start < end and stop > index]
    return " ".join(covering) if covering else span


def certainty_for(transcript: str, finding: dict[str, Any]) -> str:
    """Hedge wording anywhere in the evidence sentence forces certainty='uncertain'."""

    span = str(finding.get("evidence_span") or "")
    sentence = sentence_for_span(transcript, span)
    if hedge_in(sentence) or hedge_in(span) or "?" in sentence or "?" in span:
        return "uncertain"
    return "stated"


def ground_findings(
    transcript: str, raw_findings: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Split raw findings into grounded findings and removed claim strings."""

    kept: list[dict[str, Any]] = []
    removed: list[str] = []
    warnings: list[str] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            removed.append("unsupported claim")
            warnings.append("Removed a finding that was not an object.")
            continue
        ok, reason = finding_supported(raw, transcript)
        label = str(raw.get("finding") or raw.get("evidence_span") or "unsupported claim")
        if not ok:
            removed.append(label)
            warnings.append(f"Removed unsupported claim: {label}. {reason}.")
            continue
        finding = dict(raw)
        finding["certainty"] = certainty_for(transcript, finding)
        kept.append(finding)
    if not kept:
        warnings.append("No supported findings could be extracted from the transcript.")
    return kept, removed, warnings
