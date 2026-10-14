"""Typed chat with Viscan. Runs in-process unless --url is set."""

from __future__ import annotations

import argparse
import json

import httpx


def _print_response(payload: dict) -> None:
    print(f"\nviscan ({payload.get('provider_used')})> {payload.get('answer')}\n")
    if payload.get("needs_clarification"):
        for option in payload.get("clarification_options") or []:
            print(
                f"  - {option['patient_id']}: {option['full_name']} "
                f"(born {option['dob_year']}, last visit {option['last_visit']})"
            )
    if payload.get("warnings"):
        for warning in payload["warnings"]:
            print(f"  warning: {warning}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Viscan dental assistant CLI")
    parser.add_argument("--role", default="dentist", choices=["dentist", "radiologist", "assistant"])
    parser.add_argument("--session", default=None)
    parser.add_argument("--url", default=None, help="Talk to a running server, for example http://127.0.0.1:8000")
    args = parser.parse_args()
    session_id = args.session
    print("Viscan dental assistant. Type 'exit' to quit.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break
        if args.url:
            response = httpx.post(
                args.url.rstrip("/") + "/chat",
                json={"session_id": session_id, "text": text},
                headers={"X-User-Role": args.role},
                timeout=30,
            )
            if response.status_code >= 400:
                print(response.text)
                continue
            payload = response.json()
        else:
            from app.orchestrator import handle_text

            payload = handle_text(session_id, text, args.role)
        session_id = payload["session_id"]
        _print_response(payload)
        if payload.get("data"):
            print(json.dumps(payload["data"], indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
