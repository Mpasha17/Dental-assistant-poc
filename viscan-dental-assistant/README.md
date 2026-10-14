# Viscan dental assistant

Voice-first proof of concept for a dental clinic. A person can ask for a report, dictate a finding, ask a follow-up, or book a scan. The language model only interprets the words. Python checks the request, reads the synthetic chart, and writes the answer.

Everything in `data/` is fictional. There is no real patient information in this repository.

## What it does

- Opens a report from a sentence such as "Open Rahul's latest OPG report". Two patients named Priya produce a clarification question, not a guess. A missing study says so and lists the studies that do exist.
- Turns a dictation such as "Lower right third molar is horizontally impacted" into structured findings plus a draft. Every kept finding cites a span from the transcript. Uncertain words (`maybe`, `possibly`, `looks like`) set `certainty` to `uncertain`. The draft stays `status: draft` until a dentist or radiologist approves it.
- Remembers the open patient and report, so "Summarize his report" and "Does she have caries?" use that report. The answer says "not stated in the report" when the text does not support a yes or no.
- Proposes a scan slot and books it only after "yes, confirm". A booked slot cannot be taken twice.

## Quick start

```bash
cd viscan-dental-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

No API keys:

```bash
LLM_PROVIDER=rule STT_PROVIDER=mock uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The chat box, the hold-to-talk button, and the dictation tab all call this server. `cli.py` is the same assistant in the terminal:

```bash
LLM_PROVIDER=rule python cli.py --role dentist
```

With free keys in `.env`, leave `LLM_PROVIDER=gemini` and `STT_PROVIDER=groq`. If the key is missing, the call fails, or the provider times out, the app uses the rule interpreter and says so in `provider_used`.

## Tests

```bash
make test
```

That runs pytest with `LLM_PROVIDER=rule` and `STT_PROVIDER=mock`. No network and no API key.

## Free keys

| Provider | Where to get a key | Used for |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey | Default interpreter, model `gemini-3.1-flash-lite` |
| Groq | https://console.groq.com | Optional interpreter `openai/gpt-oss-120b`, and Whisper `whisper-large-v3-turbo` |
| Mistral | https://console.mistral.ai | Optional interpreter `mistral-small-latest` on the Experiment plan |

`faster-whisper` is the offline speech fallback. It is not installed by `requirements.txt`. Install it with `pip install -r requirements-optional.txt` and set `STT_PROVIDER=local`.

Google's free tier may use prompts to improve products. That is acceptable here because the chart is synthetic. Do not send real PHI to these tiers. See `docs/ARCHITECTURE.md`.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini`, `mistral`, `groq`, or `rule` |
| `GEMINI_API_KEY` | empty | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model id |
| `MISTRAL_API_KEY` | empty | Mistral key |
| `MISTRAL_MODEL` | `mistral-small-latest` | Mistral model id |
| `GROQ_API_KEY` | empty | Groq key, shared by chat and Whisper |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq chat model |
| `STT_PROVIDER` | `groq` | `groq`, `local`, or `mock` |
| `LOCAL_WHISPER_MODEL` | `base.en` | faster-whisper model name |
| `LLM_TIMEOUT_S` | `15` | Hosted-model timeout before the rule fallback |
| `LOG_LEVEL` | `INFO` | Python log level |
| `DEMO_DATE` | `2026-10-14` | The date used for "today" and "tomorrow" |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3-turbo` | Groq transcription model |

`GET /health` reports which provider is configured and whether each key is present. It never returns the key.

## Why these models

Gemini 3.1 Flash Lite is the default. It is on the free tier, it supports native function calls and JSON responses, and a short clinic utterance comes back in about a second. `gemini-2.5-flash` is no longer available to new keys. `gemini-3.5-flash` shares a free-tier cap of about 20 requests a day, so the lite model is the one that keeps working after that cap. Mistral Small is the second hosted option and also has tool calling on the free Experiment plan. Groq's Llama 3.3 70B is the low-latency hosted option, and the same key covers Whisper Large v3 Turbo for speech. The rule parser is the path that tests use and the path that runs when a hosted call cannot. It is deterministic, which matters more here than fluency: patient resolution, confirmation, and grounding are not left to the model.

Speech uses Groq Whisper with a dental prompt (molar, OPG, mesioangular, FDI numbers, and so on). faster-whisper `base.en` on CPU int8 is the offline substitute. The mock adapter reads a transcript field or a sidecar `.txt` file so tests never call a network.

## API

`POST /chat` accepts `{session_id, text}` and returns one response shape: answer, data, sources, clarification options, `provider_used`, and `latency_ms`. `POST /voice` accepts a webm, wav, mp3, m4a, or ogg file up to 10 MB. `POST /dictation` and `POST /dictation/audio` draft a report. `PUT /draft/{id}` edits findings. `POST /draft/{id}/approve` is limited to `X-User-Role: dentist` or `radiologist`. Text is limited to 2000 characters. A missing role header is treated as `assistant`.

## Layout

```
app/            API, interpreter, speech, tools, validation
data/           synthetic patients, reports, slots, vocabulary
static/         one-page clinic UI
tests/          offline pytest suite
docs/           architecture and a captured curl demo
cli.py          terminal chat
```

## Known limitations

- The chart and the slot book live in memory. A restart forgets bookings and drafts.
- The role is a request header. It is not authentication.
- The rule parser covers the assignment phrases and close variants. A hosted model covers more wording, then the same Python rules run.
- Tooth numbers are derived from phrases such as "lower right third molar" or from an FDI number that was actually said. Unusual shorthand may stay unnumbered.
- Dictation grounding is lexical. A paraphrase that does not share terms with the transcript is removed, even when a clinician would accept it.
- Hosted providers were implemented against the current SDKs and were not called during tests, because tests are not allowed to use the network.
- Certainty is decided by a fixed hedge list ("may", "possibly", "likely", "cannot rule out", a question mark, and similar) applied to the sentence that holds the evidence. Hedges outside that list are read as stated, and the word "may" is treated as a hedge even when it is the month.
- Mistral 429 responses are retried twice (1.5 s, then 3 s) before the rule parser takes over, so a rate-limited request can take several seconds longer. Other providers retry only a transient "unavailable" response once.
- Settings already present in the shell environment win over `.env`. A stale `export GROQ_MODEL=...` will shadow the file; the server logs `env_overrides_dotenv` with the key names when that happens.
- The microphone button needs a browser that allows `getUserMedia`. Transcription still needs `STT_PROVIDER=groq` and a Groq key, or `local`.

## What I would improve

- Persist the chart, drafts, and an audit log; replace the role header with OAuth and real RBAC.
- Run a self-hosted model under a BAA before any real PHI.
- Add a scored eval set of spoken utterances, including accents and corrections.
- Stream partial transcripts and show a diff when a clinician edits a draft.
- Read imaging from the clinic's PACS or FHIR documents instead of JSON files.

More detail is in `docs/ARCHITECTURE.md`. A captured session is in `docs/DEMO.md`.
