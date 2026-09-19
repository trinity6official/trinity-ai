from __future__ import annotations

from typing import Any

from core.events import Event


class ObjectiveEventCoordinator:
    # Bridges explicitly objective-linked ProcessManager outcomes into
    # MemoryService objective/focus state without owning execution or models.

    REVIEW_PROCESS_KIND = "objective.review"
    WATCHED_EVENTS = (
        "process.succeeded",
        "process.failed",
        "process.cancelled",
        "process.timed_out",
        "action.failed",
    )
    FAILURE_EVENTS = {"process.failed", "process.timed_out"}

    def __init__(self, host: Any) -> None:
        self.host = host
        self._started = False

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def start(self) -> None:
        if self._started:
            return
        events = getattr(self.host, "events", None)
        processes = getattr(self.host, "processes", None)
        if events is None or processes is None:
            return
        processes.register_handler(self.REVIEW_PROCESS_KIND, self._review_handler)
        for event_type in self.WATCHED_EVENTS:
            events.subscribe(event_type, self._handle_event)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        events = getattr(self.host, "events", None)
        if events is not None:
            for event_type in self.WATCHED_EVENTS:
                events.unsubscribe(event_type, self._handle_event)
        self._started = False

    def _publish(self, event_type: str, **payload: Any) -> None:
        events = getattr(self.host, "events", None)
        if events is not None:
            events.publish(event_type, **payload)

    def _audit(
        self,
        objective_id: str,
        status: str,
        *,
        metadata: dict[str, Any],
    ) -> None:
        audit = getattr(self.host, "audit", None)
        if audit is not None:
            audit.record(
                actor_type="system",
                action=f"objective.coordinate.{objective_id}",
                status=status,
                metadata=metadata,
            )

    def _process_record(self, event: Event):
        process_id = str(event.payload.get("process_id") or "").strip()
        if not process_id:
            return None
        processes = getattr(self.host, "processes", None)
        if processes is None:
            return None
        return processes.get(process_id)

    def _queue_review(
        self,
        *,
        source_event: Event,
        record,
        objective: dict[str, Any],
        reason: str,
    ) -> None:
        processes = getattr(self.host, "processes", None)
        if processes is None:
            return

        review_id = (
            f"objective-review-{record.id}-"
            f"{source_event.type.replace('.', '-')}"
        )
        if processes.get(review_id) is not None:
            return

        processes.submit(
            self.REVIEW_PROCESS_KIND,
            {
                "linked_objective_id": objective["id"],
                "objective_title": objective.get("title", ""),
                "source_event": source_event.type,
                "source_process_id": record.id,
                "source_process_kind": record.kind,
                "source_error": record.error,
                "reason": reason,
            },
            process_id=review_id,
        )
        self._publish(
            "objective.reasoning_queued",
            objective_id=objective["id"],
            source_event=source_event.type,
            source_process_id=record.id,
            review_process_id=review_id,
            reason=reason,
        )
        self._audit(
            objective["id"],
            "queued",
            metadata={
                "source_event": source_event.type,
                "source_process_id": record.id,
                "review_process_id": review_id,
                "reason": reason,
            },
        )

    def _action_execution_context(self, event: Event) -> dict[str, Any]:
        metadata = event.payload.get("metadata")
        if not isinstance(metadata, dict):
            return {}
        context = metadata.get("execution_context")
        return dict(context) if isinstance(context, dict) else {}

    def _queue_action_review(
        self,
        event: Event,
        objective: dict[str, Any],
    ) -> None:
        processes = getattr(self.host, "processes", None)
        if processes is None:
            return
        action_id = str(event.payload.get("action_id") or "").strip()
        if not action_id:
            return
        review_id = f"objective-review-action-{action_id}"
        if processes.get(review_id) is not None:
            return

        action = str(event.payload.get("action") or "unknown action")
        error = str(event.payload.get("error") or "unknown action failure")
        processes.submit(
            self.REVIEW_PROCESS_KIND,
            {
                "linked_objective_id": objective["id"],
                "objective_title": objective.get("title", ""),
                "source_event": event.type,
                "source_action_id": action_id,
                "source_action": action,
                "source_error": error,
                "reason": "current-focus action failed and needs judgment",
            },
            process_id=review_id,
        )
        self._publish(
            "objective.reasoning_queued",
            objective_id=objective["id"],
            source_event=event.type,
            source_action_id=action_id,
            review_process_id=review_id,
            reason="current-focus action failed and needs judgment",
        )
        self._audit(
            objective["id"],
            "queued",
            metadata={
                "source_event": event.type,
                "source_action_id": action_id,
                "review_process_id": review_id,
                "reason": "current-focus action failed and needs judgment",
            },
        )

    def _handle_action_failure(self, event: Event) -> None:
        context = self._action_execution_context(event)
        objective_id = str(context.get("objective_id") or "").strip()
        if not objective_id:
            return

        memory = getattr(self.host, "memory", None)
        if memory is None:
            return
        objective = memory.get_objective(objective_id)
        if objective is None:
            return
        if objective.get("status") in memory.TERMINAL_OBJECTIVE_STATUSES:
            return

        focus = memory.get_current_focus()
        if not focus or str(focus.get("id")) != objective_id:
            return

        self._queue_action_review(event, objective)

    def _handle_event(self, event: Event) -> None:
        # This synchronous EventBus path must stay cheap.
        try:
            if event.type == "action.failed":
                self._handle_action_failure(event)
                return

            record = self._process_record(event)
            if record is None or record.kind == self.REVIEW_PROCESS_KIND:
                return

            payload = dict(record.payload)
            objective_id = str(payload.get("objective_id") or "").strip()
            if not objective_id:
                return

            memory = getattr(self.host, "memory", None)
            if memory is None:
                return

            objective = memory.get_objective(objective_id)
            if objective is None:
                self._publish(
                    "objective.event_ignored",
                    objective_id=objective_id,
                    source_event=event.type,
                    source_process_id=record.id,
                    reason="objective_not_found",
                )
                return

            if objective.get("status") in memory.TERMINAL_OBJECTIVE_STATUSES:
                self._publish(
                    "objective.event_ignored",
                    objective_id=objective_id,
                    source_event=event.type,
                    source_process_id=record.id,
                    reason="objective_terminal",
                )
                return

            if (
                event.type == "process.succeeded"
                and "objective_progress_on_success" in payload
            ):
                objective = memory.update_objective_progress(
                    objective_id,
                    payload["objective_progress_on_success"],
                )
                self._publish(
                    "objective.progress_updated",
                    objective_id=objective_id,
                    source_process_id=record.id,
                    progress=objective["progress"],
                )
                self._audit(
                    objective_id,
                    "updated",
                    metadata={
                        "source_process_id": record.id,
                        "field": "progress",
                        "value": objective["progress"],
                    },
                )

            if (
                event.type in self.FAILURE_EVENTS
                and self._truthy(payload.get("objective_blocking"))
            ):
                reason = str(
                    record.error
                    or event.payload.get("error")
                    or f"{record.kind} did not complete"
                )
                objective = memory.set_objective_status(
                    objective_id,
                    "blocked",
                    reason=f"Process {record.id} blocked this objective",
                    blocked_reason=reason[:500],
                )
                self._publish(
                    "objective.blocked",
                    objective_id=objective_id,
                    source_process_id=record.id,
                    error=reason,
                )
                self._audit(
                    objective_id,
                    "updated",
                    metadata={
                        "source_process_id": record.id,
                        "field": "status",
                        "value": "blocked",
                        "reason": reason[:500],
                    },
                )

            focus = memory.get_current_focus()
            focus_id = str(focus.get("id")) if focus else ""
            explicitly_requested = self._truthy(payload.get("objective_review"))
            focused_failure = (
                event.type in self.FAILURE_EVENTS
                and focus_id == objective_id
            )

            if explicitly_requested:
                review_reason = "process explicitly requested objective review"
            elif focused_failure:
                review_reason = "current-focus process failed and needs judgment"
            else:
                return

            self._queue_review(
                source_event=event,
                record=record,
                objective=objective,
                reason=review_reason,
            )
        except Exception as exc:
            self._publish(
                "objective.coordination_failed",
                source_event=event.type,
                process_id=event.payload.get("process_id"),
                error=f"{type(exc).__name__}: {exc}",
            )

    def _review_handler(self, context, payload):
        # Deferred reasoning runs as ordinary ProcessManager work.
        context.checkpoint()
        proactive = getattr(self.host, "proactive_service", None)
        if proactive is None:
            return {
                "reviewed": False,
                "reason": "proactive_service_unavailable",
            }

        if payload.get("source_action_id"):
            source = (
                f"action={payload.get('source_action')} "
                f"({payload.get('source_action_id')})"
            )
        else:
            source = (
                f"process={payload.get('source_process_kind')} "
                f"({payload.get('source_process_id')})"
            )
        trigger = (
            "Objective-linked runtime event requires review. "
            f"Objective: {payload.get('objective_title')!r} "
            f"(id={payload.get('linked_objective_id')}). "
            f"Event: {payload.get('source_event')}; "
            f"{source}; "
            f"reason={payload.get('reason')}. "
            f"error={payload.get('source_error')!r}. "
            "Use current objective/focus context. Do not invent a new goal. "
            "Only surface something if it is genuinely useful."
        )
        proactive.check(trigger_context=trigger)
        context.checkpoint()

        self._publish(
            "objective.reasoning_completed",
            objective_id=payload.get("linked_objective_id"),
            source_process_id=payload.get("source_process_id"),
        )
        return {
            "reviewed": True,
            "objective_id": payload.get("linked_objective_id"),
            "source_process_id": payload.get("source_process_id"),
        }
