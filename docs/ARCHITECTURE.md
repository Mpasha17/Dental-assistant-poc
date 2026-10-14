# Architecture

Viscan separates interpretation from decisions. A speech adapter may turn audio into text. A language-model adapter may turn that text into one proposed tool call, or into a JSON list of dictated findings. Python then checks the call, reads the synthetic JSON chart, and builds the reply. The model never opens the data files and never marks a report final.

```mermaid
flowchart TD
  mic[Microphone or typed text] --> audio{Audio attached?}
  audio -->|yes| stt[STT adapter: Groq Whisper, faster-whisper, or mock]
  audio -->|no| text[Transcript]
  stt --> text
  text --> llm[LLM interpreter: Gemini, Mistral, Groq, or rules]
  llm --> call[Proposed tool call]
  call --> rules[Validator: allow-list, schema, role, confirmation]
  rules --> resolve[Patient resolution in Python]
  resolve -->|two close matches| ask[Clarification with candidates]
  resolve -->|one patient| tools[Deterministic tools over JSON]
  tools --> ground[Grounding and tooth map for dictation]
  ground --> draft[Draft text from a Python template]
  tools --> answer[Response with sources]
  draft --> answer
```

## Pipeline

1. `POST /voice` checks size and media type, then `STTProvider.transcribe`. `POST /chat` starts from text. The mock adapter uses the `transcript` form field or a `.txt` file with the same stem as the upload.
2. `LLMProvider.interpret` returns `{name, arguments}`. Hosted providers receive the same JSON-schema tool list from `app/tools/registry.py`. Gemini uses native function calls. Mistral and Groq use tool calls. `LLM_PROVIDER=rule` uses regex plus RapidFuzz and does not use the network.
3. If the configured provider has no key, raises, returns a rate-limit error, or exceeds `LLM_TIMEOUT_S` (15 seconds), `ProviderRouter` runs the rule parser and sets `provider_used` to `rule`.
4. `validation/rules.py` rejects unknown tools, validates arguments with Pydantic, and resolves the patient. Exact full name wins, then a unique first name, then a fuzzy score of at least 85. Two candidates within 10 points become `needs_clarification`. Report words are normalized with a synonym map: OPG includes panoramic, pano, and orthopantomogram; IOPA includes periapical x-ray; CBCT includes cone beam.
5. The tool runs only after that. `find_patient`, `list_reports`, `get_report`, `summarize_report`, and `answer_report_question` read JSON. `check_slots` lists openings. `book_slot` writes a booking only when `confirmed` is true, and the validator sets that flag only after the user says "yes, confirm". An assistant cannot skip that sentence, and cannot approve a draft.
6. Dictation is a second model call, `generate`, constrained to JSON. `validation/grounding.py` keeps a finding only when its evidence span sits in the transcript (normalized, or fuzzy at 90 or above for a long span) and the clinical terms in the finding, classification, and site appear in the transcript or in the synonym map. Anything else moves to `unsupported_claims_removed`. Tooth numbers such as FDI 48 for "lower right third molar" are filled in Python. `draft_text` is a template over the kept findings and ends with "DRAFT - requires clinician review. Not a final diagnosis."

The session stores the current patient id, the current report id, a pending clarification, and a pending slot. "Summarize his report" uses that report when the pronoun matches. A new session asks which patient. Every successful chart answer includes `sources` with report id, patient id, fields, and the quotes that were used. A question that the open report does not cover is answered "Not stated in the report."

## Privacy

The patients, reports, and slots in this repo are synthetic, and the demo date is fixed (`DEMO_DATE`, default 2026-10-14) so "tomorrow" does not depend on the wall clock. Logs go through a filter that replaces known patient names, and the request path logs ids rather than the utterance. Nothing is written to disk: sessions, drafts, and bookings disappear when the process stops.

Free tiers are not a clinical deployment. Google's free Gemini tier may use prompts to improve products. Groq and Mistral free plans are also outside a business associate agreement. A production system that saw real PHI would need a BAA or a self-hosted model, encryption, access control, and an audit log. This proof of concept does not claim those controls.

## Authorization

`X-User-Role` is `dentist`, `radiologist`, or `assistant`. A missing header is treated as assistant. Assistants can look up charts, draft, and confirm a slot the assistant was just offered. They cannot approve a draft; that route returns 403. The header is a demo stand-in. Production would use OAuth, server-side RBAC, and an audit record for every read and booking.

## Latency

The rule path is a local parse and a JSON scan, typically a few milliseconds. A hosted interpretation is usually about 0.5 to 2 seconds, and Groq Whisper is often near 1 second for a short clip, before the same Python checks run. `LLM_TIMEOUT_S` cuts off a stuck call and falls back to the rule parser. The UI shows `latency_ms` and `provider_used` on each reply. Speech is not streamed in this build.

## Costs

The default configuration is meant to stay on free tiers: Gemini Flash, Groq chat and Whisper, and Mistral's Experiment plan. Those tiers have daily or per-minute rate limits, which is why the rule parser is the automatic fallback. Paid tiers, if used later, are priced per token for the language models and per audio minute for Whisper. The rule path and the mock speech adapter cost nothing and do not leave the machine. faster-whisper also stays local, at the cost of CPU time and a lower-accuracy `base.en` model.
