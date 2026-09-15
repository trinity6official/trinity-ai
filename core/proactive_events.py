"""Deterministic event-driven proactive alerts for Trinity.

This layer intentionally does not call an LLM. It watches a small allowlist of
runtime events, suppresses noise with thresholds/cooldowns, and surfaces only
actionable signals through Trinity's existing notification and permission paths.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import time
from typing import Any, Callable

from core.events import Event


Clock = Callable[[], float]


@dataclass(frozen=True)
class ProactiveEventSignal:
    event_type: str
    key: str
    message: str
    category: str = "proactive"
    urgent: bool = False


@dataclass(frozen=True)
class ProactiveEventRule:
    event_type: str
    threshold: int
    window_seconds: float
    cooldown_seconds: float


class ProactiveEventEngine:
    """Convert selected runtime events into low-noise proactive signals."""

    RULES = {
        "scheduler.task_failed": ProactiveEventRule(
            "scheduler.task_failed", threshold=1, window_seconds=60.0, cooldown_seconds=300.0
        ),
        "tool.failed": ProactiveEventRule(
            "tool.failed", threshold=3, window_seconds=300.0, cooldown_seconds=600.0
        ),
        "voice.runtime_error": ProactiveEventRule(
            "voice.runtime_error", threshold=3, window_seconds=300.0, cooldown_seconds=600.0
        ),
        "proactive.failed": ProactiveEventRule(
            "proactive.failed", threshold=2, window_seconds=3600.0, cooldown_seconds=3600.0
        ),
        "proactive.skill_approval_required": ProactiveEventRule(
            "proactive.skill_approval_required",
            threshold=1,
            window_seconds=60.0,
            cooldown_seconds=1800.0,
        ),
    }

    def __init__(self, *, clock: Clock = time.monotonic) -> None:
        self.clock = clock
        self._recent: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._last_sent: dict[tuple[str, str], float] = {}

    @classmethod
    def watched_event_types(cls) -> tuple[str, ...]:
        return tuple(cls.RULES)

    @staticmethod
    def _event_key(event: Event) -> str:
        payload = event.payload
        if event.type == "scheduler.task_failed":
            return str(payload.get("task") or "unknown")
        if event.type == "tool.failed":
            return str(payload.get("tool") or "unknown")
        if event.type == "proactive.skill_approval_required":
            return str(payload.get("skill") or "unknown")
        return event.type

    @staticmethod
    def _message(event: Event, count: int) -> tuple[str, str, bool]:
        payload = event.payload
        if event.type == "scheduler.task_failed":
            task = str(payload.get("task") or "unknown task")
            error = str(payload.get("error") or "unknown error")
            return (
                f"Scheduled task '{task}' failed: {error[:240]}",
                "runtime",
                True,
            )
        if event.type == "tool.failed":
            tool = str(payload.get("tool") or "unknown tool")
            error = str(payload.get("error") or "unknown error")
            return (
                f"'{tool}' has failed {count} times recently. Latest error: {error[:220]}",
                "proactive",
                False,
            )
        if event.type == "voice.runtime_error":
            error = str(payload.get("error") or "unknown voice runtime error")
            return (
                f"Voice runtime has failed {count} times recently. Latest error: {error[:220]}",
                "voice",
                False,
            )
        if event.type == "proactive.failed":
            error = str(payload.get("error") or "unknown proactive error")
            return (
                f"Trinity's proactive evaluation has failed repeatedly: {error[:220]}",
                "proactive",
                False,
            )
        if event.type == "proactive.skill_approval_required":
            skill = str(payload.get("skill") or "unknown skill")
            reason = str(payload.get("reason") or "No reason supplied")
            return (
                f"Trinity identified a capability gap requiring approval: {skill} — {reason[:220]}",
                "proactive",
                False,
            )
        return (event.type, "proactive", False)

    def observe(self, event: Event) -> ProactiveEventSignal | None:
        rule = self.RULES.get(event.type)
        if rule is None:
            return None

        now = self.clock()
        key = self._event_key(event)
        bucket_key = (event.type, key)
        recent = self._recent[bucket_key]
        cutoff = now - rule.window_seconds
        while recent and recent[0] < cutoff:
            recent.popleft()
        recent.append(now)

        if len(recent) < rule.threshold:
            return None

        last_sent = self._last_sent.get(bucket_key)
        if last_sent is not None and now - last_sent < rule.cooldown_seconds:
            return None

        self._last_sent[bucket_key] = now
        message, category, urgent = self._message(event, len(recent))
        return ProactiveEventSignal(
            event_type=event.type,
            key=key,
            message=message,
            category=category,
            urgent=urgent,
        )


class ProactiveEventService:
    """Subscribe Trinity's event bus to deterministic proactive alert rules."""

    def __init__(
        self,
        host: Any,
        *,
        engine: ProactiveEventEngine | None = None,
    ) -> None:
        self.host = host
        self.engine = engine or ProactiveEventEngine()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        events = getattr(self.host, "events", None)
        if events is None:
            return
        for event_type in self.engine.watched_event_types():
            events.subscribe(event_type, self._handle_event)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        events = getattr(self.host, "events", None)
        if events is not None:
            for event_type in self.engine.watched_event_types():
                events.unsubscribe(event_type, self._handle_event)
        self._started = False

    def _handle_event(self, event: Event) -> None:
        signal = self.engine.observe(event)
        if signal is None:
            return

        permissions = getattr(self.host, "permissions", None)
        if permissions is not None:
            decision = permissions.assess_action("alert_sending")
            if not decision.allowed_autonomously:
                events = getattr(self.host, "events", None)
                if events is not None:
                    events.publish(
                        "proactive.event_suppressed",
                        source_event=signal.event_type,
                        key=signal.key,
                        reason="permission",
                    )
                return

        notifier = getattr(self.host, "notify", None)
        if not callable(notifier):
            return

        notifier(
            signal.message,
            category=signal.category,
            urgent=signal.urgent,
        )

        events = getattr(self.host, "events", None)
        if events is not None:
            events.publish(
                "proactive.event_sent",
                source_event=signal.event_type,
                key=signal.key,
                message=signal.message,
                urgent=signal.urgent,
            )
