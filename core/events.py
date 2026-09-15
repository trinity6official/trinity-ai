"""Lightweight in-process event bus for Trinity."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        # Observer failures are diagnostic data, not a reason to stop Trinity's
        # primary runtime. Keep only a bounded recent history.
        self.handler_errors: list[dict[str, str]] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event_type: str, **payload: Any) -> Event:
        event = Event(event_type, payload)
        handlers = [*self._subscribers.get(event_type, []), *self._subscribers.get("*", [])]
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                self.handler_errors.append({
                    "event_type": event_type,
                    "handler": getattr(handler, "__name__", type(handler).__name__),
                    "error": str(exc),
                })
                if len(self.handler_errors) > 100:
                    del self.handler_errors[:-100]
        return event
