"""Context awareness built on Trinity's event stream."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from core.events import Event, EventBus


@dataclass(frozen=True)
class AwarenessSnapshot:
    last_user_message: str | None
    active_tool: str | None
    last_error: str | None
    recent_event_count: int
    last_scheduler_task: str | None = None
    daemon_active: bool = False
    frontmost_app: str | None = None
    last_visual_context: str | None = None


class AwarenessEngine:
    """Maintains a compact live context from runtime events."""

    def __init__(self, bus: EventBus, history_size: int = 100) -> None:
        self.bus = bus
        self.history = deque(maxlen=history_size)
        self.last_user_message: str | None = None
        self.active_tool: str | None = None
        self.last_error: str | None = None
        self.last_scheduler_task: str | None = None
        self.daemon_active = False
        self.frontmost_app: str | None = None
        self.last_visual_context: str | None = None
        bus.subscribe("*", self._observe)

    def _observe(self, event: Event) -> None:
        self.history.append(event)
        if event.type == "message.received":
            self.last_user_message = str(event.payload.get("text", "")) or None
        elif event.type == "tool.started":
            self.active_tool = str(event.payload.get("tool", "")) or None
        elif event.type == "tool.completed":
            tool = str(event.payload.get("tool", ""))
            if not tool or tool == self.active_tool:
                self.active_tool = None
        elif event.type in {"tool.failed", "health.warning", "scheduler.task_failed", "daemon.save_failed"}:
            self.last_error = str(event.payload.get("error") or event.payload.get("message") or "") or None
        elif event.type == "scheduler.task_started":
            self.last_scheduler_task = str(event.payload.get("task", "")) or None
        elif event.type in {"scheduler.task_completed", "scheduler.task_failed"}:
            task = str(event.payload.get("task", ""))
            if not task or task == self.last_scheduler_task:
                self.last_scheduler_task = None
        elif event.type == "daemon.started":
            self.daemon_active = True
        elif event.type == "daemon.stopped":
            self.daemon_active = False
        elif event.type == "vision.screen_completed":
            app = str(event.payload.get("app_context", ""))
            if app:
                self.frontmost_app = app

    def update_visual_context(self, frontmost_app: str | None, description: str) -> None:
        """Update ephemeral visual context without publishing sensitive text as an event."""
        self.frontmost_app = frontmost_app or self.frontmost_app
        self.last_visual_context = description or None

    def snapshot(self) -> AwarenessSnapshot:
        return AwarenessSnapshot(
            last_user_message=self.last_user_message,
            active_tool=self.active_tool,
            last_error=self.last_error,
            recent_event_count=len(self.history),
            last_scheduler_task=self.last_scheduler_task,
            daemon_active=self.daemon_active,
            frontmost_app=self.frontmost_app,
            last_visual_context=self.last_visual_context,
        )

    def recent(self, event_type: str | None = None, limit: int = 10) -> list[Event]:
        events = list(self.history)
        if event_type is not None:
            events = [event for event in events if event.type == event_type]
        return events[-limit:]
