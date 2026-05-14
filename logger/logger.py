"""
logger/logger.py — Module de journalisation IRIS ENCODE.

API définie, aucun backend branché en v1.
Backend prévu : fichier JSON ou SQLite dans une release ultérieure.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


class _IrisLogger:
    """Logger inerte — les appels sont acceptés mais rien n'est écrit."""

    def __init__(self) -> None:
        self._session_id: str = ""

    def session_start(self, profile: str, path: str, **kw: Any) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        self._session_id = f"{ts}-{profile}"

    def session_end(self, total: int, success: int, skipped: int, **kw: Any) -> None:
        pass

    def info(self, message: str, **kw: Any) -> None:
        pass

    def warning(self, message: str, **kw: Any) -> None:
        pass

    def error(self, message: str, **kw: Any) -> None:
        pass

    def encode_start(self, file: str, action: str, **kw: Any) -> None:
        pass

    def encode_end(self, file: str, success: bool, duration_s: float, **kw: Any) -> None:
        pass


# Singleton exporté
logger = _IrisLogger()
