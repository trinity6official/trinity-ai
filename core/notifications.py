"""Local-first notification routing for Trinity."""
from __future__ import annotations

from dataclasses import dataclass

from core.events import EventBus


@dataclass(frozen=True)
class NotificationResult:
    event_created: bool
    voice_spoken: bool = False


class NotificationService:
    """Publish runtime notifications locally, with optional local speech."""

    def __init__(self, event_bus: EventBus, *, voice=None) -> None:
        self.event_bus = event_bus
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

        voice_spoken = False
        if speak and self.voice is not None:
            try:
                voice_spoken = bool(self.voice.speak(message))
            except Exception:
                voice_spoken = False
        return NotificationResult(True, voice_spoken)
