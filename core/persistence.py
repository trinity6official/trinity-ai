"""Local persistence coordinator for Trinity state."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PersistenceReport:
    success: bool
    saved_at: str
    brain_path: str | None = None
    error: str | None = None


class StatePersistence:
    """Persist Trinity state locally; Git is not a memory database."""

    def __init__(self, consciousness, memory_store=None) -> None:
        self.consciousness = consciousness
        self.memory_store = memory_store

    def save(self) -> PersistenceReport:
        now = datetime.now(timezone.utc).isoformat()
        try:
            self.consciousness.save()
            brain_path = getattr(self.consciousness, "brain_path", None)
            return PersistenceReport(
                True,
                saved_at=now,
                brain_path=str(brain_path) if brain_path is not None else None,
            )
        except Exception as exc:
            return PersistenceReport(False, saved_at=now, error=str(exc))
