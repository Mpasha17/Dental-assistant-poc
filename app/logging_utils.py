"""Logging that keeps patient names out of the log stream."""

from __future__ import annotations

import logging
import re

_CONFIGURED = False


class PatientNameRedactionFilter(logging.Filter):
    """Replace known synthetic patient names with a redaction token.

    The filter fails open: a lookup error must not drop the log record.
    """

    def __init__(self) -> None:
        super().__init__()
        self._patterns: list[tuple[re.Pattern[str], str]] | None = None
        self._busy = False

    def _compiled(self) -> list[tuple[re.Pattern[str], str]]:
        if self._patterns is not None:
            return self._patterns
        names: list[str] = []
        try:
            from app.tools.store import patients

            for patient in patients():
                names.append(patient["full_name"])
                names.append(patient["last_name"])
        except Exception:
            names = []
        ordered = sorted({name for name in names if len(name) > 2}, key=len, reverse=True)
        self._patterns = [
            (re.compile(re.escape(name), re.IGNORECASE), "[REDACTED]") for name in ordered
        ]
        return self._patterns

    def filter(self, record: logging.LogRecord) -> bool:
        if self._busy:
            return True
        self._busy = True
        try:
            message = record.getMessage()
            for pattern, replacement in self._compiled():
                message = pattern.sub(replacement, message)
            record.msg = message
            record.args = ()
        except Exception:
            return True
        finally:
            self._busy = False
        return True


def get_logger() -> logging.Logger:
    return logging.getLogger("viscan")


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Attach one redacting handler to the viscan logger."""

    global _CONFIGURED
    logger = get_logger()
    logger.setLevel(level.upper())
    logger.propagate = False
    if not any(isinstance(item, PatientNameRedactionFilter) for item in logger.filters):
        logger.addFilter(PatientNameRedactionFilter())
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        _CONFIGURED = True
    return logger
