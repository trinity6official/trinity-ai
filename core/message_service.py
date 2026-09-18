"""Channel-neutral incoming message orchestration for Trinity."""
from __future__ import annotations

from typing import Any, Callable

from core.commands import CommandHandler
from core.orchestrator import MessageKind, MessageOrchestrator


class MessageService:
    """Own intent routing, approval flow and conversation dispatch."""

    def __init__(self, host: Any) -> None:
        self.host = host

    @staticmethod
    def _complete(events, kind: str) -> None:
        if events is not None:
            events.publish("message.completed", kind=kind)

    def handle(
        self,
        text: str,
        *,
        responder: Callable[[str], Any] | None = None,
        source: str = "local",
    ) -> str | None:
        """Bind the originating interface, then run the shared message pipeline."""
        output = getattr(self.host, "output", None)
        if output is None:
            return self._handle_bound(text, responder=responder, source=source)
        with output.route(responder, source=source):
            return self._handle_bound(text, responder=responder, source=source)

    def _handle_bound(
        self,
        text: str,
        *,
        responder: Callable[[str], Any] | None,
        source: str,
    ) -> str | None:
        h = self.host
        text = text.strip()
        output = getattr(h, "output", None)
        reply = getattr(h, "respond", None) if output is not None else (responder or getattr(h, "respond", None))
        if not callable(reply):
            raise RuntimeError("No response route is configured for this message")
        events = getattr(h, "events", None)
        if events is not None:
            events.publish("message.received", text=text, source=source)

        lang_info = h.language.detect_and_respond(text)
        language = lang_info["language"]
        h.memory.update_david_last_seen()
        h.consciousness.add_working(f"David said: {text[:200]}", priority="high")

        pending = h.skills.get_pending_changes()
        evolution = getattr(h, "skill_evolution", None)
        evolution_pending = evolution.get_pending_changes() if evolution is not None else {}
        get_pending_actions = getattr(h.skills, "get_pending_actions", None)
        action_pending = get_pending_actions() if callable(get_pending_actions) else {}
        if not isinstance(action_pending, dict):
            action_pending = {}
        orchestrator = getattr(h, "orchestrator", MessageOrchestrator())
        intent = orchestrator.classify(
            text, has_pending_change=bool(pending or evolution_pending or action_pending)
        )

        if intent.kind == MessageKind.APPROVAL and evolution_pending:
            proposal_id = list(evolution_pending.keys())[-1]
            success, message = evolution.approve(proposal_id)
            response = ("Done!\n\n" if success else "Approval failed: ") + message
            reply(response)
            h.consciousness.log_decision(
                decision=f"Apply Trinity skill proposal {proposal_id}",
                reasoning="David explicitly approved the pending skill improvement",
                alternatives=["Cancel proposal", "Keep proposal pending"],
                confidence=0.99,
                context="Skill evolution approval flow",
            )
            h.consciousness.save()
            self._complete(events, "approval")
            return response

        if intent.kind == MessageKind.APPROVAL and action_pending:
            approval_id = list(action_pending.keys())[-1]
            action = action_pending[approval_id]
            result = h.skills.approve_action(approval_id)
            success = not (isinstance(result, dict) and result.get("success") is False)
            if success:
                output = result.get("output") if isinstance(result, dict) else str(result)
                response = f"Done!\n\n{output or 'Approved action completed.'}"
            else:
                response = f"Approved action failed: {result.get('error', 'unknown error')}"
            reply(response)
            h.consciousness.log_decision(
                decision=f"Approve {action.get('skill')}.{action.get('tool')}",
                reasoning="David explicitly approved the pending action",
                alternatives=["Cancel action"],
                confidence=0.99,
                context="Generic tool approval flow",
            )
            h.consciousness.save()
            self._complete(events, "approval")
            return response

        if intent.kind == MessageKind.APPROVAL and pending:
            change_id = list(pending.keys())[-1]
            change = pending[change_id]
            h.consciousness.log_decision(
                decision=f"Commit change to {change.get('repo')}/{change.get('path')}",
                reasoning="David approved the pending change",
                alternatives=["Wait for more changes", "Cancel"],
                confidence=0.95,
                context="David approval flow",
            )
            success, message = h.skills.commit_change(change_id)
            if success:
                response = f"Done!\n\n{message}"
                reply(response)
                h.memory.record_decision(
                    f"Committed change to {change.get('repo')}/{change.get('path')}",
                    "David approved",
                )
                h.consciousness.remember(
                    f"Committed change to {change.get('repo')}/{change.get('path')}: {message[:100]}",
                    "episodic", tags=["github", "commit", "approved"],
                    outcome="success", importance=0.7,
                )
            else:
                response = f"Commit failed: {message}"
                reply(response)
                h.consciousness.remember(
                    f"Commit failed for {change.get('repo')}/{change.get('path')}: {message[:100]}",
                    "episodic", tags=["github", "commit", "failed"],
                    outcome="failure", importance=0.8,
                )
            h.consciousness.save()
            self._complete(events, "approval")
            return response

        if intent.kind == MessageKind.REJECTION and evolution_pending:
            proposal_id = list(evolution_pending.keys())[-1]
            evolution.cancel(proposal_id)
            response = "Skill improvement cancelled. No code was changed."
            reply(response)
            h.consciousness.remember(
                f"David cancelled skill improvement proposal {proposal_id}", "episodic",
                tags=["skill_build", "cancelled"], outcome="success", importance=0.4,
            )
            h.consciousness.save()
            self._complete(events, "rejection")
            return response

        if intent.kind == MessageKind.REJECTION and action_pending:
            approval_id = list(action_pending.keys())[-1]
            h.skills.cancel_action(approval_id)
            response = "Action cancelled. Nothing was executed."
            reply(response)
            h.consciousness.remember(
                f"David cancelled pending action {approval_id}", "episodic",
                tags=["action", "cancelled"], outcome="success", importance=0.4,
            )
            h.consciousness.save()
            self._complete(events, "rejection")
            return response

        if intent.kind == MessageKind.REJECTION and pending:
            change_id = list(pending.keys())[-1]
            h.skills.cancel_change(change_id)
            response = "Change cancelled. No commits made."
            reply(response)
            h.consciousness.remember(
                "David cancelled pending change", "episodic",
                tags=["github", "cancelled"], outcome="success", importance=0.4,
            )
            h.consciousness.save()
            self._complete(events, "rejection")
            return response

        command_handler = getattr(h, "commands", CommandHandler(h))
        handled_command = (
            command_handler.handle(intent.command or text, language)
            if intent.kind == MessageKind.COMMAND else False
        )

        response = None
        if not handled_command:
            thinking = h.language.get_response_prefix(language)["thinking"]
            reply(thinking)
            response = h.clean_response_for_david(h.ask_trinity(text, language))
            reply(response)

        h.consciousness.save()
        self._complete(events, "command" if handled_command else "conversation")
        return response
