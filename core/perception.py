"""Ephemeral local perception for Trinity.

Screen/image bytes and model descriptions are kept in memory only. They are not
written to Trinity's memory vault, action audit, or general event stream. The
awareness engine may receive the current textual description through an explicit
in-memory context sink.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from core.audit import ActionAuditTrail
from core.computer import ComputerController
from core.events import EventBus
from core.vision import LocalVisionService


VisualContextSink = Callable[[str | None, str], None]


@dataclass(frozen=True)
class PerceptionResult:
    success: bool
    description: str = ""
    app_context: str | None = None
    error: str | None = None
    action_id: str | None = None
    skipped: bool = False
    reason: str | None = None


class PerceptionService:
    """Join local screen observation with local multimodal inference safely."""

    def __init__(
        self,
        computer: ComputerController,
        vision: LocalVisionService,
        *,
        event_bus: EventBus | None = None,
        audit_trail: ActionAuditTrail | None = None,
        context_sink: VisualContextSink | None = None,
    ) -> None:
        self.computer = computer
        self.vision = vision
        self.events = event_bus
        self.audit = audit_trail
        self.context_sink = context_sink
        self._last_image_hash: str | None = None

    def _record(self, status: str, *, action_id: str | None = None, **kwargs: Any) -> str | None:
        if self.audit is None:
            return action_id
        return self.audit.record(
            actor_type="vision",
            action="vision.analyze_screen",
            status=status,
            action_id=action_id,
            permission="safe",
            approved=True,
            **kwargs,
        )

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self.events is not None:
            self.events.publish(event_type, **payload)

    def analyze_screen(
        self,
        prompt: str = (
            "Describe what is visible and identify anything relevant to the current task. "
            "Focus on the active application, visible errors/status, and what may need attention. "
            "Do not infer hidden information or secrets."
        ),
        *,
        force: bool = False,
    ) -> PerceptionResult:
        action_id = self._record("requested", params={"prompt_chars": len(prompt)})
        self._record("started", action_id=action_id)
        self._emit("vision.screen_started")

        if not self.vision.available():
            error = "Local vision model is unavailable"
            self._record("failed", action_id=action_id, error=error)
            self._emit("vision.screen_failed", error=error)
            return PerceptionResult(False, error=error, action_id=action_id)

        capture = self.computer.capture_screen()
        if not capture.success or not capture.image:
            error = capture.error or "Screen capture failed"
            self._record("failed", action_id=action_id, error=error)
            self._emit("vision.screen_failed", error=error)
            return PerceptionResult(False, error=error, action_id=action_id)

        image_hash = hashlib.sha256(capture.image).hexdigest()
        if not force and image_hash == self._last_image_hash:
            self._record(
                "completed",
                action_id=action_id,
                result={"skipped": True, "reason": "unchanged"},
            )
            self._emit("vision.screen_skipped", reason="unchanged")
            return PerceptionResult(
                True,
                action_id=action_id,
                skipped=True,
                reason="unchanged",
            )

        app_context = None
        app = self.computer.frontmost_app()
        if app.success and app.output:
            app_context = app.output

        effective_prompt = prompt
        if app_context:
            effective_prompt = f"Frontmost application: {app_context}.\n\n{prompt}"

        try:
            description = self.vision.analyze(capture.image, effective_prompt, capture.media_type)
        except Exception as exc:
            error = str(exc)
            self._record("failed", action_id=action_id, error=error)
            self._emit("vision.screen_failed", error=error)
            return PerceptionResult(False, app_context=app_context, error=error, action_id=action_id)

        self._last_image_hash = image_hash
        if self.context_sink is not None:
            self.context_sink(app_context, description)

        # Only metadata enters audit/events; never screenshot bytes or model description.
        self._record(
            "completed",
            action_id=action_id,
            result={
                "description_chars": len(description),
                "app_context": app_context or "",
                "image_hash": image_hash,
            },
        )
        self._emit(
            "vision.screen_completed",
            description_chars=len(description),
            app_context=app_context or "",
            image_hash=image_hash,
        )
        return PerceptionResult(
            True,
            description=description,
            app_context=app_context,
            action_id=action_id,
        )
