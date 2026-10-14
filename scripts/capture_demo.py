"""Start a fresh server, run the curl demo, and write docs/DEMO.md from the responses."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "DEMO.md"
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"
ENV = {
    **os.environ,
    "LLM_PROVIDER": "rule",
    "STT_PROVIDER": "mock",
    "DEMO_DATE": "2026-10-14",
    "LOG_LEVEL": "INFO",
}


def _curl(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["curl", "-sS", "-w", "\n__HTTP__%{http_code}", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    raw = completed.stdout
    if "__HTTP__" not in raw:
        return completed.returncode or 1, completed.stderr or raw
    body, _, status = raw.rpartition("\n__HTTP__")
    try:
        code = int(status.strip())
    except ValueError:
        code = 0
    return code, body


def _pretty(body: str) -> str:
    try:
        return json.dumps(json.loads(body), indent=2)
    except json.JSONDecodeError:
        return body


def main() -> None:
    python = ROOT / ".venv" / "bin" / "python"
    if not python.is_file():
        python = Path(os.environ.get("PYTHON", "python3"))
    server = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(BASE + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.2)
        else:
            output = server.stdout.read() if server.stdout else ""
            raise SystemExit("server did not start\n" + output)

        sections: list[str] = [
            "# Demo",
            "",
            "These responses were captured by `scripts/capture_demo.py` against a fresh",
            "server with `LLM_PROVIDER=rule`, `STT_PROVIDER=mock`, and `DEMO_DATE=2026-10-14`.",
            "The clinic date is Wednesday 14 October 2026, so \"tomorrow morning\" is 15 October.",
            "Restart the server before repeating the booking steps. Slots live in memory.",
            "",
            "```bash",
            "LLM_PROVIDER=rule STT_PROVIDER=mock DEMO_DATE=2026-10-14 \\",
            "  uvicorn app.main:app --host 127.0.0.1 --port 8000",
            "```",
            "",
        ]

        def add(title: str, command: str, args: list[str]) -> dict | None:
            code, body = _curl(args)
            sections.extend(
                [
                    f"## {title}",
                    "",
                    "```bash",
                    command,
                    "```",
                    "",
                    f"HTTP {code}",
                    "",
                    "```json",
                    _pretty(body),
                    "```",
                    "",
                ]
            )
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return None

        role = ["-H", "X-User-Role: dentist", "-H", "Content-Type: application/json"]
        add("Health", f"curl -sS {BASE}/health", ["-sS", f"{BASE}/health"])
        add("Patients", f"curl -sS {BASE}/patients", ["-sS", f"{BASE}/patients"])
        add(
            "Rahul's latest OPG",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"text":"Open Rahul'"'"'s latest OPG report"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"text": "Open Rahul's latest OPG report"})],
        )
        add(
            "Priya Sharma's newer OPG",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"priya-sharma","text":"Open Priya Sharma'"'"'s latest OPG"}}'""",
            [
                *role,
                f"{BASE}/chat",
                "-d",
                json.dumps({"session_id": "priya-sharma", "text": "Open Priya Sharma's latest OPG"}),
            ],
        )
        add(
            "Ambiguous Priya",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"ambig","text":"Open Priya'"'"'s latest OPG report"}}'""",
            [
                *role,
                f"{BASE}/chat",
                "-d",
                json.dumps({"session_id": "ambig", "text": "Open Priya's latest OPG report"}),
            ],
        )
        add(
            "Resolve Priya Shah",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"ambig","text":"Priya Shah"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"session_id": "ambig", "text": "Priya Shah"})],
        )
        add(
            "Kavya has no OPG",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"text":"Open Kavya'"'"'s latest OPG report"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"text": "Open Kavya's latest OPG report"})],
        )
        add(
            "Open a report for follow-up",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"follow","text":"Open Rahul'"'"'s latest OPG report"}}'""",
            [
                *role,
                f"{BASE}/chat",
                "-d",
                json.dumps({"session_id": "follow", "text": "Open Rahul's latest OPG report"}),
            ],
        )
        add(
            "Summarize his report",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"follow","text":"Summarize his report"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"session_id": "follow", "text": "Summarize his report"})],
        )
        add(
            "Question the report does not answer",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"follow","text":"Does he have caries?"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"session_id": "follow", "text": "Does he have caries?"})],
        )
        add(
            "Question the report does answer",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"priya-sharma","text":"Does she have caries?"}}'""",
            [
                *role,
                f"{BASE}/chat",
                "-d",
                json.dumps({"session_id": "priya-sharma", "text": "Does she have caries?"}),
            ],
        )
        add(
            "Summarize with no context",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"text":"Summarize his report"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"text": "Summarize his report"})],
        )
        draft = add(
            "Dictation: horizontal impaction",
            f"""curl -sS {BASE}/dictation -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"transcript":"Lower right third molar is horizontally impacted"}}'""",
            [
                *role,
                f"{BASE}/dictation",
                "-d",
                json.dumps({"transcript": "Lower right third molar is horizontally impacted"}),
            ],
        )
        add(
            "Dictation: uncertain caries",
            f"""curl -sS {BASE}/dictation -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"transcript":"Possibly caries on the upper left first molar"}}'""",
            [
                *role,
                f"{BASE}/dictation",
                "-d",
                json.dumps({"transcript": "Possibly caries on the upper left first molar"}),
            ],
        )
        draft_id = ((draft or {}).get("data") or {}).get("report_id", "draft-missing")
        add(
            "Assistant cannot approve",
            f"""curl -sS -X POST {BASE}/draft/{draft_id}/approve -H 'X-User-Role: assistant'""",
            ["-X", "POST", "-H", "X-User-Role: assistant", f"{BASE}/draft/{draft_id}/approve"],
        )
        add(
            "Dentist approves the draft",
            f"""curl -sS -X POST {BASE}/draft/{draft_id}/approve -H 'X-User-Role: dentist'""",
            ["-X", "POST", "-H", "X-User-Role: dentist", f"{BASE}/draft/{draft_id}/approve"],
        )
        add(
            "Propose a booking",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"book","text":"Book an OPG for Rahul tomorrow morning"}}'""",
            [
                *role,
                f"{BASE}/chat",
                "-d",
                json.dumps({"session_id": "book", "text": "Book an OPG for Rahul tomorrow morning"}),
            ],
        )
        add(
            "Confirm the booking",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"book","text":"yes, confirm"}}'""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"session_id": "book", "text": "yes, confirm"})],
        )
        add(
            "Already booked slot",
            f"""curl -sS {BASE}/chat -H 'X-User-Role: dentist' -H 'Content-Type: application/json' \\
  -d '{{"session_id":"book2","text":"Book slot S001 for Ananya Iyer"}}'""",
            [
                *role,
                f"{BASE}/chat",
                "-d",
                json.dumps({"session_id": "book2", "text": "Book slot S001 for Ananya Iyer"}),
            ],
        )
        add(
            "Text over 2000 characters",
            f"""python - << 'PY'
import json, urllib.request
body = json.dumps({{"text": "a" * 2001}}).encode()
request = urllib.request.Request("{BASE}/chat", data=body, headers={{"Content-Type": "application/json"}})
try:
    urllib.request.urlopen(request)
except Exception as exc:
    print(exc)
PY
# The captured call below is the same oversized body via curl.""",
            [*role, f"{BASE}/chat", "-d", json.dumps({"text": "a" * 2001})],
        )
        with tempfile.NamedTemporaryFile(suffix=".txt") as handle:
            handle.write(b"not audio")
            handle.flush()
            add(
                "Rejected audio type",
                f"""curl -sS {BASE}/voice -H 'X-User-Role: dentist' \\
  -F 'audio=@note.txt;type=text/plain' \\
  -F 'transcript=Open Rahul'"'"'s latest OPG report'""",
                [
                    "-H",
                    "X-User-Role: dentist",
                    "-F",
                    f"audio=@{handle.name};type=text/plain",
                    "-F",
                    "transcript=Open Rahul's latest OPG report",
                    f"{BASE}/voice",
                ],
            )
        with tempfile.NamedTemporaryFile(suffix=".webm") as handle:
            handle.write(b"\x1a\x45\xdf\xa3fake")
            handle.flush()
            add(
                "Mock voice with a transcript field",
                f"""curl -sS {BASE}/voice -H 'X-User-Role: dentist' \\
  -F 'audio=@speech.webm;type=audio/webm' \\
  -F 'session_id=voice' \\
  -F 'transcript=Open Rahul'"'"'s latest OPG report'""",
                [
                    "-H",
                    "X-User-Role: dentist",
                    "-F",
                    f"audio=@{handle.name};type=audio/webm",
                    "-F",
                    "session_id=voice",
                    "-F",
                    "transcript=Open Rahul's latest OPG report",
                    f"{BASE}/voice",
                ],
            )
        add(
            "Fetch one stored report",
            f"curl -sS {BASE}/reports/R007",
            [f"{BASE}/reports/R007"],
        )
        DOCS.write_text("\n".join(sections), encoding="utf-8")
        print(f"wrote {DOCS}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
