"""Local-first notification routing for Trinity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.events import EventBus


@dataclass(frozen=True)
class NotificationResult:
    event_created: bool
    telegram_sent: bool = False
    voice_spoken: bool = False


class NotificationService:
    """Publish runtime notifications locally, with optional remote delivery."""

    def __init__(self, event_bus: EventBus, *, telegram=None, voice=None) -> None:
        self.event_bus = event_bus
        self.telegram = telegram
        self.voice = voice

    def notify(
        self,
        message: str,
        *,
        category: str = "general",
        urgent: bool = False,
        speak: bool = False,
    ) -> NotificationResult:
        self.event_bus.publish(
            "notification.created",
            message=message,
            category=category,
            urgent=urgent,
        )
        telegram_sent = False
        if self.telegram is not None and getattr(self.telegram, "remote_notifications", False):
            telegram_sent = bool(self.telegram.send(message))

        voice_spoken = False
        if speak and self.voice is not None:
            try:
                voice_spoken = bool(self.voice.speak(message))
            except Exception:
                voice_spoken = False
        return NotificationResult(True, telegram_sent, voice_spoken)
