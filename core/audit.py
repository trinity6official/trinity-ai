"""Persistent action audit trail for Trinity.

The audit trail is intentionally independent of consciousness/memory. It records
security-relevant execution state for skills and agents as append-only JSONL and
optionally mirrors those records onto Trinity's in-process event bus.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.events import EventBus


_REDACTED = "<redacted>"
_SENSITIVE_PARTS = (
    "token", "secret", "password", "passwd", "api_key", "apikey",
    "authorization", "cookie", "private_key", "credential",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def sanitize(value: Any, *, max_string: int = 500, depth: int = 0) -> Any:
    """Return a JSON-safe, redacted representation suitable for audit logs."""
    if depth > 5:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_string else value[:max_string] + "…"
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            cleaned[key_str] = (
                _REDACTED
                if _is_sensitive_key(key_str)
                else sanitize(item, max_string=max_string, depth=depth + 1)
            )
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item, max_string=max_string, depth=depth + 1) for item in value]
    return sanitize(str(value), max_string=max_string, depth=depth + 1)


class ActionAuditTrail:
    """Append-only audit trail shared by skills, agents and future executors."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = "memory/runtime/action_audit.jsonl",
        *,
        event_bus: EventBus | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.event_bus = event_bus

    def record(
        self,
        *,
        actor_type: str,
        action: str,
        status: str,
        action_id: str | None = None,
        permission: str | None = None,
        approved: bool | None = None,
        params: Any = None,
        result: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        action_id = action_id or uuid4().hex
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_id": action_id,
            "actor_type": actor_type,
            "action": action,
            "status": status,
        }
        if permission is not None:
            entry["permission"] = permission
        if approved is not None:
            entry["approved"] = bool(approved)
        if params is not None:
            entry["params"] = sanitize(params)
        if result is not None:
            entry["result"] = sanitize(result)
        if error is not None:
            entry["error"] = sanitize(error)
        if metadata:
            entry["metadata"] = sanitize(metadata)

        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

        if self.event_bus is not None:
            self.event_bus.publish(f"action.{status}", **entry)
        return action_id
