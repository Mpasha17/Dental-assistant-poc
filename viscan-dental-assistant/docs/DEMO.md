# Demo

These responses were captured by `scripts/capture_demo.py` against a fresh
server with `LLM_PROVIDER=rule`, `STT_PROVIDER=mock`, and `DEMO_DATE=2026-10-14`.
The clinic date is Wednesday 14 October 2026, so "tomorrow morning" is 15 October.
Restart the server before repeating the booking steps. Slots live in memory.

```bash
LLM_PROVIDER=rule STT_PROVIDER=mock DEMO_DATE=2026-10-14 \
  uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Health

```bash
curl -sS http://127.0.0.1:8000/health
```

HTTP 200

```json
{
  "status": "ok",
  "llm_provider": "rule",
  "stt_provider": "mock",
  "gemini_model": "gemini-2.5-flash",
  "mistral_model": "mistral-small-latest",
  "groq_model": "llama-3.3-70b-versatile",
  "groq_whisper_model": "whisper-large-v3-turbo",
  "local_whisper_model": "base.en",
  "llm_timeout_s": 15.0,
  "demo_date": "2026-10-14",
  "keys": {
    "gemini": false,
    "mistral": false,
    "groq": false
  }
}
```

## Patients

```bash
curl -sS http://127.0.0.1:8000/patients
```

HTTP 200

```json
{
  "patients": [
    {
      "id": "P001",
      "patient_id": "P001",
      "full_name": "Priya Sharma",
      "first_name": "Priya",
      "last_name": "Sharma",
      "sex": "F",
      "dob": "1990-04-18",
      "dob_year": 1990,
      "pronoun": "her",
      "last_visit": "2026-09-20"
    },
    {
      "id": "P002",
      "patient_id": "P002",
      "full_name": "Priya Shah",
      "first_name": "Priya",
      "last_name": "Shah",
      "sex": "F",
      "dob": "1985-11-02",
      "dob_year": 1985,
      "pronoun": "her",
      "last_visit": "2026-07-12"
    },
    {
      "id": "P003",
      "patient_id": "P003",
      "full_name": "Rahul Verma",
      "first_name": "Rahul",
      "last_name": "Verma",
      "sex": "M",
      "dob": "1978-01-30",
      "dob_year": 1978,
      "pronoun": "his",
      "last_visit": "2026-08-19"
    },
    {
      "id": "P004",
      "patient_id": "P004",
      "full_name": "Ananya Iyer",
      "first_name": "Ananya",
      "last_name": "Iyer",
      "sex": "F",
      "dob": "2001-08-09",
      "dob_year": 2001,
      "pronoun": "her",
      "last_visit": "2026-05-02"
    },
    {
      "id": "P005",
      "patient_id": "P005",
      "full_name": "Mohammed Irfan",
      "first_name": "Mohammed",
      "last_name": "Irfan",
      "sex": "M",
      "dob": "1995-06-07",
      "dob_year": 1995,
      "pronoun": "his",
      "last_visit": "2026-03-20"
    },
    {
      "id": "P006",
      "patient_id": "P006",
      "full_name": "Kavya Reddy",
      "first_name": "Kavya",
      "last_name": "Reddy",
      "sex": "F",
      "dob": "1988-12-25",
      "dob_year": 1988,
      "pronoun": "her",
      "last_visit": "2026-09-01"
    }
  ]
}
```

## Rahul's latest OPG

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"text":"Open Rahul'"'"'s latest OPG report"}'
```

HTTP 200

```json
{
  "session_id": "fad4e585729d476d999117b9b3b8eb1b",
  "intent": "retrieve_report",
  "answer": "Rahul Verma's latest OPG report is R007 dated 2026-08-19.\nClinician: Dr. Sameer Qureshi\nFindings:\n- Lower right third molar is horizontally impacted (FDI 48)\n- Mild bone loss around the lower incisors\nImpression: Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
  "data": {
    "found": true,
    "patient_id": "P003",
    "patient": {
      "id": "P003",
      "patient_id": "P003",
      "full_name": "Rahul Verma",
      "first_name": "Rahul",
      "last_name": "Verma",
      "sex": "M",
      "dob": "1978-01-30",
      "dob_year": 1978,
      "pronoun": "his",
      "last_visit": "2026-08-19"
    },
    "report": {
      "id": "R007",
      "patient_id": "P003",
      "type": "OPG",
      "date": "2026-08-19",
      "clinician": "Dr. Sameer Qureshi",
      "findings": [
        {
          "description": "Lower right third molar is horizontally impacted",
          "site": "lower right third molar",
          "fdi_tooth": "48",
          "universal_tooth": "32"
        },
        {
          "description": "Mild bone loss around the lower incisors",
          "site": "lower incisors",
          "fdi_tooth": null,
          "universal_tooth": null
        }
      ],
      "impression": "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
      "recommendations": [
        "Surgical opinion for tooth 48.",
        "Oral hygiene review."
      ]
    },
    "which": "latest"
  },
  "sources": [
    {
      "report_id": "R007",
      "patient_id": "P003",
      "fields": [
        "type",
        "date",
        "findings",
        "impression",
        "recommendations"
      ],
      "quotes": [
        "Lower right third molar is horizontally impacted",
        "Mild bone loss around the lower incisors",
        "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss."
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 1,
  "warnings": []
}
```

## Priya Sharma's newer OPG

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"priya-sharma","text":"Open Priya Sharma'"'"'s latest OPG"}'
```

HTTP 200

```json
{
  "session_id": "priya-sharma",
  "intent": "retrieve_report",
  "answer": "Priya Sharma's latest OPG report is R002 dated 2026-09-20.\nClinician: Dr. Neha Kapoor\nFindings:\n- Occlusal caries on the upper left first molar (FDI 26)\n- Horizontal impaction of the lower right third molar is unchanged (FDI 48)\nImpression: Caries on the upper left first molar (FDI 26). Horizontal impaction of tooth 48 is unchanged from the April study.",
  "data": {
    "found": true,
    "patient_id": "P001",
    "patient": {
      "id": "P001",
      "patient_id": "P001",
      "full_name": "Priya Sharma",
      "first_name": "Priya",
      "last_name": "Sharma",
      "sex": "F",
      "dob": "1990-04-18",
      "dob_year": 1990,
      "pronoun": "her",
      "last_visit": "2026-09-20"
    },
    "report": {
      "id": "R002",
      "patient_id": "P001",
      "type": "OPG",
      "date": "2026-09-20",
      "clinician": "Dr. Neha Kapoor",
      "findings": [
        {
          "description": "Occlusal caries on the upper left first molar",
          "site": "upper left first molar",
          "fdi_tooth": "26",
          "universal_tooth": "14"
        },
        {
          "description": "Horizontal impaction of the lower right third molar is unchanged",
          "site": "lower right third molar",
          "fdi_tooth": "48",
          "universal_tooth": "32"
        }
      ],
      "impression": "Caries on the upper left first molar (FDI 26). Horizontal impaction of tooth 48 is unchanged from the April study.",
      "recommendations": [
        "Restore tooth 26.",
        "Review the impaction of tooth 48."
      ]
    },
    "which": "latest"
  },
  "sources": [
    {
      "report_id": "R002",
      "patient_id": "P001",
      "fields": [
        "type",
        "date",
        "findings",
        "impression",
        "recommendations"
      ],
      "quotes": [
        "Occlusal caries on the upper left first molar",
        "Horizontal impaction of the lower right third molar is unchanged",
        "Caries on the upper left first molar (FDI 26). Horizontal impaction of tooth 48 is unchanged from the April study."
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Ambiguous Priya

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"ambig","text":"Open Priya'"'"'s latest OPG report"}'
```

HTTP 200

```json
{
  "session_id": "ambig",
  "intent": "clarify_patient",
  "answer": "I found more than one patient matching \"Priya\". Which patient do you mean?",
  "data": null,
  "sources": [],
  "needs_clarification": true,
  "clarification_options": [
    {
      "patient_id": "P001",
      "full_name": "Priya Sharma",
      "dob_year": 1990,
      "last_visit": "2026-09-20"
    },
    {
      "patient_id": "P002",
      "full_name": "Priya Shah",
      "dob_year": 1985,
      "last_visit": "2026-07-12"
    }
  ],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Resolve Priya Shah

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"ambig","text":"Priya Shah"}'
```

HTTP 200

```json
{
  "session_id": "ambig",
  "intent": "retrieve_report",
  "answer": "Priya Shah's latest OPG report is R004 dated 2026-07-11.\nClinician: Dr. Lila Fernandes\nFindings:\n- Missing upper right third molar with a healed socket (FDI 18)\n- Mucosal thickening of the right maxillary sinus\nImpression: Edentulous site at tooth 18. No acute osseous lesion identified on this panoramic view.",
  "data": {
    "found": true,
    "patient_id": "P002",
    "patient": {
      "id": "P002",
      "patient_id": "P002",
      "full_name": "Priya Shah",
      "first_name": "Priya",
      "last_name": "Shah",
      "sex": "F",
      "dob": "1985-11-02",
      "dob_year": 1985,
      "pronoun": "her",
      "last_visit": "2026-07-12"
    },
    "report": {
      "id": "R004",
      "patient_id": "P002",
      "type": "OPG",
      "date": "2026-07-11",
      "clinician": "Dr. Lila Fernandes",
      "findings": [
        {
          "description": "Missing upper right third molar with a healed socket",
          "site": "upper right third molar",
          "fdi_tooth": "18",
          "universal_tooth": "1"
        },
        {
          "description": "Mucosal thickening of the right maxillary sinus",
          "site": "right maxillary sinus",
          "fdi_tooth": null,
          "universal_tooth": null
        }
      ],
      "impression": "Edentulous site at tooth 18. No acute osseous lesion identified on this panoramic view.",
      "recommendations": [
        "No radiographic follow-up is required for the healed 18 site."
      ]
    },
    "which": "latest"
  },
  "sources": [
    {
      "report_id": "R004",
      "patient_id": "P002",
      "fields": [
        "type",
        "date",
        "findings",
        "impression",
        "recommendations"
      ],
      "quotes": [
        "Missing upper right third molar with a healed socket",
        "Mucosal thickening of the right maxillary sinus",
        "Edentulous site at tooth 18. No acute osseous lesion identified on this panoramic view."
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Kavya has no OPG

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"text":"Open Kavya'"'"'s latest OPG report"}'
```

HTTP 200

```json
{
  "session_id": "93d25b4f7ab242de848f0b6c9d2728b9",
  "intent": "missing_report",
  "answer": "No OPG report found for Kavya Reddy. Available reports: CBCT (2026-09-01, R017), Bitewing (2026-06-18, R016), IOPA (2026-06-18, R015).",
  "data": {
    "patient_id": "P006",
    "patient": {
      "id": "P006",
      "patient_id": "P006",
      "full_name": "Kavya Reddy",
      "first_name": "Kavya",
      "last_name": "Reddy",
      "sex": "F",
      "dob": "1988-12-25",
      "dob_year": 1988,
      "pronoun": "her",
      "last_visit": "2026-09-01"
    },
    "requested_type": "OPG",
    "available_reports": [
      {
        "id": "R017",
        "report_id": "R017",
        "patient_id": "P006",
        "type": "CBCT",
        "date": "2026-09-01",
        "clinician": "Dr. Arjun Mehta"
      },
      {
        "id": "R016",
        "report_id": "R016",
        "patient_id": "P006",
        "type": "Bitewing",
        "date": "2026-06-18",
        "clinician": "Dr. Neha Kapoor"
      },
      {
        "id": "R015",
        "report_id": "R015",
        "patient_id": "P006",
        "type": "IOPA",
        "date": "2026-06-18",
        "clinician": "Dr. Neha Kapoor"
      }
    ],
    "report": null
  },
  "sources": [
    {
      "report_id": "R017",
      "patient_id": "P006",
      "fields": [
        "type",
        "date"
      ],
      "quotes": []
    },
    {
      "report_id": "R016",
      "patient_id": "P006",
      "fields": [
        "type",
        "date"
      ],
      "quotes": []
    },
    {
      "report_id": "R015",
      "patient_id": "P006",
      "fields": [
        "type",
        "date"
      ],
      "quotes": []
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Open a report for follow-up

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"follow","text":"Open Rahul'"'"'s latest OPG report"}'
```

HTTP 200

```json
{
  "session_id": "follow",
  "intent": "retrieve_report",
  "answer": "Rahul Verma's latest OPG report is R007 dated 2026-08-19.\nClinician: Dr. Sameer Qureshi\nFindings:\n- Lower right third molar is horizontally impacted (FDI 48)\n- Mild bone loss around the lower incisors\nImpression: Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
  "data": {
    "found": true,
    "patient_id": "P003",
    "patient": {
      "id": "P003",
      "patient_id": "P003",
      "full_name": "Rahul Verma",
      "first_name": "Rahul",
      "last_name": "Verma",
      "sex": "M",
      "dob": "1978-01-30",
      "dob_year": 1978,
      "pronoun": "his",
      "last_visit": "2026-08-19"
    },
    "report": {
      "id": "R007",
      "patient_id": "P003",
      "type": "OPG",
      "date": "2026-08-19",
      "clinician": "Dr. Sameer Qureshi",
      "findings": [
        {
          "description": "Lower right third molar is horizontally impacted",
          "site": "lower right third molar",
          "fdi_tooth": "48",
          "universal_tooth": "32"
        },
        {
          "description": "Mild bone loss around the lower incisors",
          "site": "lower incisors",
          "fdi_tooth": null,
          "universal_tooth": null
        }
      ],
      "impression": "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
      "recommendations": [
        "Surgical opinion for tooth 48.",
        "Oral hygiene review."
      ]
    },
    "which": "latest"
  },
  "sources": [
    {
      "report_id": "R007",
      "patient_id": "P003",
      "fields": [
        "type",
        "date",
        "findings",
        "impression",
        "recommendations"
      ],
      "quotes": [
        "Lower right third molar is horizontally impacted",
        "Mild bone loss around the lower incisors",
        "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss."
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Summarize his report

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"follow","text":"Summarize his report"}'
```

HTTP 200

```json
{
  "session_id": "follow",
  "intent": "summarize_report",
  "answer": "OPG report R007 dated 2026-08-19 for Rahul Verma, read by Dr. Sameer Qureshi. Findings: Lower right third molar is horizontally impacted; Mild bone loss around the lower incisors. Impression: Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss. Recommendations: Surgical opinion for tooth 48; Oral hygiene review.",
  "data": {
    "patient_id": "P003",
    "report_id": "R007",
    "summary": "OPG report R007 dated 2026-08-19 for Rahul Verma, read by Dr. Sameer Qureshi. Findings: Lower right third molar is horizontally impacted; Mild bone loss around the lower incisors. Impression: Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss. Recommendations: Surgical opinion for tooth 48; Oral hygiene review.",
    "report": {
      "id": "R007",
      "report_id": "R007",
      "patient_id": "P003",
      "type": "OPG",
      "date": "2026-08-19",
      "clinician": "Dr. Sameer Qureshi"
    }
  },
  "sources": [
    {
      "report_id": "R007",
      "patient_id": "P003",
      "fields": [
        "findings",
        "impression",
        "recommendations"
      ],
      "quotes": [
        "Lower right third molar is horizontally impacted",
        "Mild bone loss around the lower incisors",
        "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss."
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Question the report does not answer

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"follow","text":"Does he have caries?"}'
```

HTTP 200

```json
{
  "session_id": "follow",
  "intent": "answer_question",
  "answer": "Not stated in the report.",
  "data": {
    "patient_id": "P003",
    "report_id": "R007",
    "stated": false,
    "report": {
      "id": "R007",
      "report_id": "R007",
      "patient_id": "P003",
      "type": "OPG",
      "date": "2026-08-19",
      "clinician": "Dr. Sameer Qureshi"
    }
  },
  "sources": [
    {
      "report_id": "R007",
      "patient_id": "P003",
      "fields": [],
      "quotes": []
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Question the report does answer

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"priya-sharma","text":"Does she have caries?"}'
```

HTTP 200

```json
{
  "session_id": "priya-sharma",
  "intent": "answer_question",
  "answer": "Yes. The report states: \"Caries on the upper left first molar (FDI 26). Horizontal impaction of tooth 48 is unchanged from the April study.\"",
  "data": {
    "patient_id": "P001",
    "report_id": "R002",
    "stated": true,
    "report": {
      "id": "R002",
      "report_id": "R002",
      "patient_id": "P001",
      "type": "OPG",
      "date": "2026-09-20",
      "clinician": "Dr. Neha Kapoor"
    }
  },
  "sources": [
    {
      "report_id": "R002",
      "patient_id": "P001",
      "fields": [
        "impression",
        "findings"
      ],
      "quotes": [
        "Caries on the upper left first molar (FDI 26). Horizontal impaction of tooth 48 is unchanged from the April study.",
        "Occlusal caries on the upper left first molar"
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Summarize with no context

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"text":"Summarize his report"}'
```

HTTP 200

```json
{
  "session_id": "f5c5f51369324648bac2638bc27e33c1",
  "intent": "clarify_patient",
  "answer": "Which patient's report should I use?",
  "data": null,
  "sources": [],
  "needs_clarification": true,
  "clarification_options": [
    {
      "patient_id": "P001",
      "full_name": "Priya Sharma",
      "dob_year": 1990,
      "last_visit": "2026-09-20"
    },
    {
      "patient_id": "P002",
      "full_name": "Priya Shah",
      "dob_year": 1985,
      "last_visit": "2026-07-12"
    },
    {
      "patient_id": "P003",
      "full_name": "Rahul Verma",
      "dob_year": 1978,
      "last_visit": "2026-08-19"
    },
    {
      "patient_id": "P004",
      "full_name": "Ananya Iyer",
      "dob_year": 2001,
      "last_visit": "2026-05-02"
    },
    {
      "patient_id": "P005",
      "full_name": "Mohammed Irfan",
      "dob_year": 1995,
      "last_visit": "2026-03-20"
    },
    {
      "patient_id": "P006",
      "full_name": "Kavya Reddy",
      "dob_year": 1988,
      "last_visit": "2026-09-01"
    }
  ],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Dictation: horizontal impaction

```bash
curl -sS http://127.0.0.1:8000/dictation -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"transcript":"Lower right third molar is horizontally impacted"}'
```

HTTP 200

```json
{
  "session_id": "9073d0cadf01467d8466e18049514d7c",
  "intent": "draft_report",
  "answer": "CLINICAL DRAFT REPORT\nPatient: unassigned\n\nFindings:\n1. Lower right third molar (FDI 48, Universal 32): Lower right third molar is horizontally impacted [classification: horizontal; certainty: stated]\n   Evidence: \"Lower right third molar is horizontally impacted\"\n\nDRAFT - requires clinician review. Not a final diagnosis.",
  "data": {
    "report_id": "draft-8a9b116b-9cc6-4ae3-a573-abff94989a44",
    "patient_id": null,
    "status": "draft",
    "requires_clinician_review": true,
    "findings": [
      {
        "finding": "Lower right third molar is horizontally impacted",
        "anatomical_site": {
          "description": "Lower right third molar",
          "jaw": "mandible",
          "quadrant": "lower right",
          "fdi_tooth": "48",
          "universal_tooth": "32"
        },
        "classification": "horizontal",
        "certainty": "stated",
        "evidence_span": "Lower right third molar is horizontally impacted"
      }
    ],
    "draft_text": "CLINICAL DRAFT REPORT\nPatient: unassigned\n\nFindings:\n1. Lower right third molar (FDI 48, Universal 32): Lower right third molar is horizontally impacted [classification: horizontal; certainty: stated]\n   Evidence: \"Lower right third molar is horizontally impacted\"\n\nDRAFT - requires clinician review. Not a final diagnosis.",
    "warnings": [],
    "unsupported_claims_removed": [],
    "transcript": "Lower right third molar is horizontally impacted"
  },
  "sources": [
    {
      "report_id": "draft-8a9b116b-9cc6-4ae3-a573-abff94989a44",
      "patient_id": null,
      "fields": [
        "transcript",
        "findings"
      ],
      "quotes": [
        "Lower right third molar is horizontally impacted"
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": true,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": "Lower right third molar is horizontally impacted",
  "latency_ms": 1,
  "warnings": []
}
```

## Dictation: uncertain caries

```bash
curl -sS http://127.0.0.1:8000/dictation -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"transcript":"Possibly caries on the upper left first molar"}'
```

HTTP 200

```json
{
  "session_id": "f0f40f4a6b1f40298be8de61d74bbd9e",
  "intent": "draft_report",
  "answer": "CLINICAL DRAFT REPORT\nPatient: unassigned\n\nFindings:\n1. upper left first molar (FDI 26, Universal 14): caries on the upper left first molar [classification: caries; certainty: uncertain]\n   Evidence: \"Possibly caries on the upper left first molar\"\n\nDRAFT - requires clinician review. Not a final diagnosis.",
  "data": {
    "report_id": "draft-57960a37-4368-4333-943b-cd10e7ff6837",
    "patient_id": null,
    "status": "draft",
    "requires_clinician_review": true,
    "findings": [
      {
        "finding": "caries on the upper left first molar",
        "anatomical_site": {
          "description": "upper left first molar",
          "jaw": "maxilla",
          "quadrant": "upper left",
          "fdi_tooth": "26",
          "universal_tooth": "14"
        },
        "classification": "caries",
        "certainty": "uncertain",
        "evidence_span": "Possibly caries on the upper left first molar"
      }
    ],
    "draft_text": "CLINICAL DRAFT REPORT\nPatient: unassigned\n\nFindings:\n1. upper left first molar (FDI 26, Universal 14): caries on the upper left first molar [classification: caries; certainty: uncertain]\n   Evidence: \"Possibly caries on the upper left first molar\"\n\nDRAFT - requires clinician review. Not a final diagnosis.",
    "warnings": [],
    "unsupported_claims_removed": [],
    "transcript": "Possibly caries on the upper left first molar"
  },
  "sources": [
    {
      "report_id": "draft-57960a37-4368-4333-943b-cd10e7ff6837",
      "patient_id": null,
      "fields": [
        "transcript",
        "findings"
      ],
      "quotes": [
        "Possibly caries on the upper left first molar"
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": true,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": "Possibly caries on the upper left first molar",
  "latency_ms": 0,
  "warnings": []
}
```

## Assistant cannot approve

```bash
curl -sS -X POST http://127.0.0.1:8000/draft/draft-8a9b116b-9cc6-4ae3-a573-abff94989a44/approve -H 'X-User-Role: assistant'
```

HTTP 403

```json
{
  "error": "Assistants cannot approve a draft"
}
```

## Dentist approves the draft

```bash
curl -sS -X POST http://127.0.0.1:8000/draft/draft-8a9b116b-9cc6-4ae3-a573-abff94989a44/approve -H 'X-User-Role: dentist'
```

HTTP 200

```json
{
  "data": {
    "report_id": "draft-8a9b116b-9cc6-4ae3-a573-abff94989a44",
    "patient_id": null,
    "status": "approved",
    "requires_clinician_review": false,
    "findings": [
      {
        "finding": "Lower right third molar is horizontally impacted",
        "anatomical_site": {
          "description": "Lower right third molar",
          "jaw": "mandible",
          "quadrant": "lower right",
          "fdi_tooth": "48",
          "universal_tooth": "32"
        },
        "classification": "horizontal",
        "certainty": "stated",
        "evidence_span": "Lower right third molar is horizontally impacted"
      }
    ],
    "draft_text": "CLINICAL DRAFT REPORT\nPatient: unassigned\n\nFindings:\n1. Lower right third molar (FDI 48, Universal 32): Lower right third molar is horizontally impacted [classification: horizontal; certainty: stated]\n   Evidence: \"Lower right third molar is horizontally impacted\"\n\nDRAFT - requires clinician review. Not a final diagnosis.",
    "warnings": [],
    "unsupported_claims_removed": [],
    "transcript": "Lower right third molar is horizontally impacted",
    "approved_by_role": "dentist"
  },
  "answer": "Draft approved.",
  "requires_clinician_review": false
}
```

## Propose a booking

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"book","text":"Book an OPG for Rahul tomorrow morning"}'
```

HTTP 200

```json
{
  "session_id": "book",
  "intent": "propose_booking",
  "answer": "I can book an OPG for Rahul Verma on 2026-10-15 at 09:00 (slot S001). Say \"yes, confirm\" to book it. I have not booked it yet.",
  "data": {
    "booked": false,
    "patient_id": "P003",
    "patient": {
      "id": "P003",
      "patient_id": "P003",
      "full_name": "Rahul Verma",
      "first_name": "Rahul",
      "last_name": "Verma",
      "sex": "M",
      "dob": "1978-01-30",
      "dob_year": 1978,
      "pronoun": "his",
      "last_visit": "2026-08-19"
    },
    "proposed_slot": {
      "id": "S001",
      "scan_type": "OPG",
      "date": "2026-10-15",
      "time": "09:00",
      "part_of_day": "morning",
      "booked": false,
      "patient_id": null
    }
  },
  "sources": [],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Confirm the booking

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"book","text":"yes, confirm"}'
```

HTTP 200

```json
{
  "session_id": "book",
  "intent": "confirm_booking",
  "answer": "Booked OPG for Rahul Verma on 2026-10-15 at 09:00 (slot S001).",
  "data": {
    "booked": true,
    "patient_id": "P003",
    "slot": {
      "id": "S001",
      "scan_type": "OPG",
      "date": "2026-10-15",
      "time": "09:00",
      "part_of_day": "morning",
      "booked": true,
      "patient_id": "P003"
    }
  },
  "sources": [],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Already booked slot

```bash
curl -sS http://127.0.0.1:8000/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \
  -d '{"session_id":"book2","text":"Book slot S001 for Ananya Iyer"}'
```

HTTP 200

```json
{
  "session_id": "book2",
  "intent": "booking_unavailable",
  "answer": "Slot S001 is already booked. I did not book it again.",
  "data": {
    "booked": false,
    "slot": {
      "id": "S001",
      "scan_type": "OPG",
      "date": "2026-10-15",
      "time": "09:00",
      "part_of_day": "morning",
      "booked": true,
      "patient_id": "P003"
    },
    "reason": "already_booked"
  },
  "sources": [],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": null,
  "transcript": null,
  "latency_ms": 0,
  "warnings": []
}
```

## Text over 2000 characters

```bash
python - << 'PY'
import json, urllib.request
body = json.dumps({"text": "a" * 2001}).encode()
request = urllib.request.Request("http://127.0.0.1:8000/chat", data=body, headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(request)
except Exception as exc:
    print(exc)
PY
# The captured call below is the same oversized body via curl.
```

HTTP 422

```json
{
  "error": "Invalid request",
  "detail": "text: String should have at most 2000 characters"
}
```

## Rejected audio type

```bash
curl -sS http://127.0.0.1:8000/voice -H 'X-User-Role: dentist' \
  -F 'audio=@note.txt;type=text/plain' \
  -F 'transcript=Open Rahul'"'"'s latest OPG report'
```

HTTP 415

```json
{
  "error": "Unsupported audio type. Use webm, wav, mp3, m4a, or ogg."
}
```

## Mock voice with a transcript field

```bash
curl -sS http://127.0.0.1:8000/voice -H 'X-User-Role: dentist' \
  -F 'audio=@speech.webm;type=audio/webm' \
  -F 'session_id=voice' \
  -F 'transcript=Open Rahul'"'"'s latest OPG report'
```

HTTP 200

```json
{
  "session_id": "voice",
  "intent": "retrieve_report",
  "answer": "Rahul Verma's latest OPG report is R007 dated 2026-08-19.\nClinician: Dr. Sameer Qureshi\nFindings:\n- Lower right third molar is horizontally impacted (FDI 48)\n- Mild bone loss around the lower incisors\nImpression: Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
  "data": {
    "found": true,
    "patient_id": "P003",
    "patient": {
      "id": "P003",
      "patient_id": "P003",
      "full_name": "Rahul Verma",
      "first_name": "Rahul",
      "last_name": "Verma",
      "sex": "M",
      "dob": "1978-01-30",
      "dob_year": 1978,
      "pronoun": "his",
      "last_visit": "2026-08-19"
    },
    "report": {
      "id": "R007",
      "patient_id": "P003",
      "type": "OPG",
      "date": "2026-08-19",
      "clinician": "Dr. Sameer Qureshi",
      "findings": [
        {
          "description": "Lower right third molar is horizontally impacted",
          "site": "lower right third molar",
          "fdi_tooth": "48",
          "universal_tooth": "32"
        },
        {
          "description": "Mild bone loss around the lower incisors",
          "site": "lower incisors",
          "fdi_tooth": null,
          "universal_tooth": null
        }
      ],
      "impression": "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
      "recommendations": [
        "Surgical opinion for tooth 48.",
        "Oral hygiene review."
      ]
    },
    "which": "latest"
  },
  "sources": [
    {
      "report_id": "R007",
      "patient_id": "P003",
      "fields": [
        "type",
        "date",
        "findings",
        "impression",
        "recommendations"
      ],
      "quotes": [
        "Lower right third molar is horizontally impacted",
        "Mild bone loss around the lower incisors",
        "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss."
      ]
    }
  ],
  "needs_clarification": false,
  "clarification_options": [],
  "requires_clinician_review": false,
  "provider_used": "rule",
  "stt_provider": "mock",
  "transcript": "Open Rahul's latest OPG report",
  "latency_ms": 0,
  "warnings": []
}
```

## Fetch one stored report

```bash
curl -sS http://127.0.0.1:8000/reports/R007
```

HTTP 200

```json
{
  "report": {
    "id": "R007",
    "patient_id": "P003",
    "type": "OPG",
    "date": "2026-08-19",
    "clinician": "Dr. Sameer Qureshi",
    "findings": [
      {
        "description": "Lower right third molar is horizontally impacted",
        "site": "lower right third molar",
        "fdi_tooth": "48",
        "universal_tooth": "32"
      },
      {
        "description": "Mild bone loss around the lower incisors",
        "site": "lower incisors",
        "fdi_tooth": null,
        "universal_tooth": null
      }
    ],
    "impression": "Horizontal impaction of the mandibular right third molar. Mild mandibular anterior bone loss.",
    "recommendations": [
      "Surgical opinion for tooth 48.",
      "Oral hygiene review."
    ]
  },
  "draft": false
}
```
