"""Event-driven Trinity presence state.

Presence is a projection of real runtime events, not an independent animation
state machine. That keeps local UI, voice and automation status synchronized.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Callable

from core.events import Event, EventBus


class PresenceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SEARCHING = "searching"
    USING_TOOL = "using_tool"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True)
class PresenceSnapshot:
    state: PresenceState
    detail: str
    since: str
    last_activity: str
    active_tool: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class PresenceEngine:
    """Derive Trinity's visible state from the shared event bus."""

    def __init__(
        self,
        events: EventBus,
        *,
        done_duration: float = 0.8,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.events = events
        self._lock = RLock()
        self._clock = clock
        self._done_duration = max(0.0, float(done_duration))
        self._done_until: float | None = None
        now = self._now()
        self._snapshot = PresenceSnapshot(PresenceState.IDLE, "Ready", now, now)
        events.subscribe("*", self._observe)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _set(
        self,
        state: PresenceState,
        detail: str,
        *,
        active_tool: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            now = self._now()
            previous = self._snapshot
            since = previous.since if previous.state == state else now
            self._snapshot = PresenceSnapshot(
                state=state,
                detail=detail,
                since=since,
                last_activity=now,
                active_tool=active_tool,
                error=error,
            )
            self._done_until = (
                self._clock() + self._done_duration
                if state == PresenceState.DONE else None
            )

    def _observe(self, event: Event) -> None:
        kind = event.type
        payload = event.payload

        if kind == "voice.state":
            voice_state = str(payload.get("state", "")).lower()
            mapping = {
                "idle": (PresenceState.IDLE, "Ready"),
                "listening": (PresenceState.LISTENING, "Listening"),
                "thinking": (PresenceState.THINKING, "Thinking"),
                "speaking": (PresenceState.SPEAKING, "Speaking"),
                "interrupted": (PresenceState.LISTENING, "Interrupted — listening"),
                "error": (PresenceState.ERROR, "Voice error"),
            }
            if voice_state in mapping:
                state, detail = mapping[voice_state]
                self._set(state, detail, error="Voice error" if state == PresenceState.ERROR else None)
            return

        if kind == "message.received":
            self._set(PresenceState.THINKING, "Understanding request")
            return
        if kind in {"message.completed", "conversation.completed"}:
            # Briefly expose completion so local UI can acknowledge a finished turn.
            # Voice may immediately override this with SPEAKING when appropriate.
            self._set(PresenceState.DONE, "Done")
            return

        if kind in {"search.started", "web.search_started"}:
            self._set(PresenceState.SEARCHING, "Searching")
            return

        if kind == "tool.started":
            tool = str(payload.get("tool", "")) or None
            normalized = (tool or "").lower()
            state = (
                PresenceState.SEARCHING
                if "search" in normalized or normalized.startswith("web.")
                else PresenceState.USING_TOOL
            )
            detail = f"Searching with {tool}" if state == PresenceState.SEARCHING else f"Using {tool or 'tool'}"
            self._set(state, detail, active_tool=tool)
            return
        if kind == "tool.completed":
            self._set(PresenceState.THINKING, "Processing result")
            return
        if kind == "tool.failed":
            error = str(payload.get("error", "Tool failed"))
            self._set(PresenceState.ERROR, "Tool failed", error=error)
            return

        if kind == "action.started":
            actor = str(payload.get("actor_type", "action"))
            action = str(payload.get("action", "")) or actor
            normalized = action.lower()
            if "search" in normalized or normalized.startswith("web."):
                state = PresenceState.SEARCHING
            else:
                state = PresenceState.USING_TOOL if actor == "skill" else PresenceState.EXECUTING
            detail = f"Searching with {action}" if state == PresenceState.SEARCHING else f"Executing {action}"
            self._set(state, detail, active_tool=action)
            return
        if kind == "action.failed":
            error = str(payload.get("error", "Action failed"))
            self._set(PresenceState.ERROR, "Action failed", error=error)
            return

        if kind in {"health.warning", "scheduler.task_failed", "proactive.failed", "vision.screen_failed"}:
            error = str(payload.get("error") or payload.get("message") or "Runtime warning")
            self._set(PresenceState.ERROR, "Attention needed", error=error)

    def snapshot(self) -> PresenceSnapshot:
        with self._lock:
            if (
                self._snapshot.state == PresenceState.DONE
                and self._done_until is not None
                and self._clock() >= self._done_until
            ):
                self._set(PresenceState.IDLE, "Ready")
            return self._snapshot

    def clear_error(self) -> None:
        self._set(PresenceState.IDLE, "Ready")
