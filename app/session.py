"""In-memory conversation context. Nothing here is written to disk."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Session:
    """Remembers the current patient, report, and any question still open."""

    id: str
    patient_id: str | None = None
    report_id: str | None = None
    pending_clarification: dict[str, Any] | None = None
    pending_booking: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, session_id: str | None) -> Session:
        """Return the named session, or create one when the id is new or empty."""

        if not session_id:
            session_id = uuid4().hex
        session = self._sessions.get(session_id)
        if session is None:
            session = Session(id=session_id)
            self._sessions[session_id] = session
        return session

    def clear(self) -> None:
        self._sessions.clear()


session_store = SessionStore()
