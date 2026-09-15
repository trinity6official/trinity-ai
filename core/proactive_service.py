"""Proactive reasoning loop for Trinity."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any, Callable

from core.proactive import ProactiveEngine
from core.models import ChatMessage


class ProactiveService:
    """Evaluate context and emit only useful proactive messages."""

    def __init__(
        self,
        host: Any,
        *,
        now: Callable[[], datetime] = datetime.now,
        clock: Callable[[], float] = time.monotonic,
        duplicate_window_seconds: float = 6 * 3600,
    ) -> None:
        self.host = host
        self.now = now
        self.clock = clock
        self.duplicate_window_seconds = duplicate_window_seconds
        self._last_message_hash: str | None = None
        self._last_message_at: float = 0.0

    def check(self) -> None:
        h = self.host
        try:
            llm = h.llm
            if not llm:
                return
            engine = getattr(h, "proactive", ProactiveEngine())
            awareness = getattr(h, "awareness", None)
            awareness_context = ""
            if awareness is not None:
                snapshot = awareness.snapshot()
                awareness_context = (
                    f"last_user_message={snapshot.last_user_message!r}; "
                    f"active_tool={snapshot.active_tool!r}; "
                    f"last_error={snapshot.last_error!r}; "
                    f"recent_events={snapshot.recent_event_count}; "
                    f"scheduler_task={snapshot.last_scheduler_task!r}; "
                    f"daemon_active={snapshot.daemon_active}; "
                    f"frontmost_app={snapshot.frontmost_app!r}; "
                    f"visual_context={snapshot.last_visual_context!r}"
                )

            prompt = engine.build_prompt(
                now=self.now().strftime("%A, %d %B at %H:%M"),
                consciousness_context=h.consciousness.get_context(),
                company_context=h.memory.get_full_context(),
                awareness_context=awareness_context,
            )
            response = h._invoke_with_failover(
                [
                    ChatMessage("system", "You are Trinity. Be selective and genuinely useful."),
                    ChatMessage("user", prompt),
                ],
                preferred_llm=llm,
            )
            decision = engine.parse(response.content)
            events = getattr(h, "events", None)
            if decision.silent:
                print("[INITIATIVE] Nothing proactive to share right now.")
                if events is not None:
                    events.publish("proactive.silent")
                return

            for request in decision.skill_requests:
                # Proactive reasoning may identify a capability gap, but self-modifying
                # code is never performed silently. Surface it for explicit approval.
                if events is not None:
                    events.publish(
                        "proactive.skill_approval_required",
                        skill=request.name, reason=request.reason,
                    )

            if decision.message:
                normalized = " ".join(decision.message.lower().split())
                digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                now_seconds = self.clock()
                if (
                    digest == self._last_message_hash
                    and now_seconds - self._last_message_at < self.duplicate_window_seconds
                ):
                    if events is not None:
                        events.publish("proactive.suppressed", reason="duplicate")
                    return

                permissions = getattr(h, "permissions", None)
                if permissions is not None:
                    decision_policy = permissions.assess_action("alert_sending")
                    if not decision_policy.allowed_autonomously:
                        if events is not None:
                            events.publish("proactive.suppressed", reason="permission")
                        return

                print(f"[INITIATIVE] Proactive message: {decision.message[:120]}...")
                notifier = getattr(h, "notify", None)
                if callable(notifier):
                    notifier(decision.message, category="proactive")
                else:
                    h.send_telegram(decision.message)
                self._last_message_hash = digest
                self._last_message_at = now_seconds
                if events is not None:
                    events.publish("proactive.sent", message=decision.message)
                h.consciousness.remember(
                    f"Proactive initiative sent: {decision.message[:200]}", "episodic",
                    tags=["proactive", "initiative"], outcome="success", importance=0.5,
                )
        except Exception as exc:
            print(f"[INITIATIVE] Error in proactive check: {exc}")
            events = getattr(h, "events", None)
            if events is not None:
                events.publish("proactive.failed", error=str(exc))
