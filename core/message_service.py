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

    @staticmethod
    def _pending_approval_candidates(
        github_pending,
        evolution_pending,
        action_pending,
        mcp_pending,
    ):
        candidates = []
        for approval_id, item in evolution_pending.items():
            candidates.append(("evolution", approval_id, item))
        for approval_id, item in mcp_pending.items():
            candidates.append(("mcp", approval_id, item))
        for approval_id, item in action_pending.items():
            candidates.append(("action", approval_id, item))
        for approval_id, item in github_pending.items():
            candidates.append(("github", approval_id, item))
        return candidates

    @staticmethod
    def _pending_candidate_label(candidate) -> str:
        kind, approval_id, item = candidate
        if kind == "evolution":
            detail = (
                f"skill improvement {item.get('skill_name', '')} "
                f"({item.get('path', '')})"
            ).strip()
        elif kind == "mcp":
            detail = (
                f"MCP {item.get('server', '')}.{item.get('tool', '')}"
            )
        elif kind == "action":
            detail = (
                f"action {item.get('skill', '')}.{item.get('tool', '')}"
            )
        else:
            detail = (
                f"GitHub change {item.get('repo', '')}/{item.get('path', '')}"
            )
        return f"{approval_id} | {detail}"

    def _resolve_pending_approval(
        self,
        *,
        intent,
        github_pending,
        evolution_pending,
        action_pending,
        mcp_pending,
    ):
        candidates = self._pending_approval_candidates(
            github_pending,
            evolution_pending,
            action_pending,
            mcp_pending,
        )
        reference = str(getattr(intent, "approval_id", "") or "").strip()

        if reference:
            matches = [
                candidate
                for candidate in candidates
                if str(candidate[1]) == reference
            ]
            if len(matches) == 1:
                return matches[0], None
            if not matches:
                return None, (
                    f"No pending approval matches ID {reference}. "
                    "Use /pending to see the current approval IDs."
                )
            return None, (
                f"Approval ID {reference} is ambiguous. "
                "Use /pending to review the current approvals."
            )

        if len(candidates) == 1:
            return candidates[0], None

        if len(candidates) > 1:
            choices = "\n".join(
                f"- {self._pending_candidate_label(candidate)}"
                for candidate in candidates
            )
            return None, (
                "Multiple approvals are pending. I won't guess which one you mean.\n\n"
                f"{choices}\n\n"
                "Reply APPROVE <id> or REJECT <id>."
            )

        return None, None

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
        mcp_execution = getattr(h, "mcp_execution", None)
        mcp_pending = mcp_execution.get_pending_actions() if mcp_execution is not None else {}
        orchestrator = getattr(h, "orchestrator", MessageOrchestrator())
        intent = orchestrator.classify(
            text, has_pending_change=bool(pending or evolution_pending or action_pending or mcp_pending)
        )

        if intent.kind in {MessageKind.APPROVAL, MessageKind.REJECTION}:
            selected, selection_error = self._resolve_pending_approval(
                intent=intent,
                github_pending=pending,
                evolution_pending=evolution_pending,
                action_pending=action_pending,
                mcp_pending=mcp_pending,
            )
            if selection_error:
                reply(selection_error)
                self._complete(events, "approval_selection")
                return selection_error
            if selected is not None:
                selected_kind, selected_id, _selected_item = selected
                pending = (
                    {selected_id: pending[selected_id]}
                    if selected_kind == "github" else {}
                )
                evolution_pending = (
                    {selected_id: evolution_pending[selected_id]}
                    if selected_kind == "evolution" else {}
                )
                action_pending = (
                    {selected_id: action_pending[selected_id]}
                    if selected_kind == "action" else {}
                )
                mcp_pending = (
                    {selected_id: mcp_pending[selected_id]}
                    if selected_kind == "mcp" else {}
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

        if intent.kind == MessageKind.APPROVAL and mcp_pending:
            approval_id = list(mcp_pending.keys())[-1]
            action = mcp_pending[approval_id]
            result = mcp_execution.approve_action(approval_id)
            success = bool(isinstance(result, dict) and result.get("success"))
            response = (
                f"Done!\n\n{result.get('output', 'Approved MCP action completed.')}"
                if success else f"Approved MCP action failed: {result.get('error', 'unknown error')}"
            )
            reply(response)
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

        if intent.kind == MessageKind.REJECTION and mcp_pending:
            approval_id = list(mcp_pending.keys())[-1]
            mcp_execution.cancel_action(approval_id)
            response = "MCP action cancelled. Nothing was executed."
            reply(response)
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
            # Preserve command arguments; MessageIntent.command intentionally stores
            # only the normalized first token for classification.
            command_handler.handle(getattr(intent, "text", None) or text, language)
            if intent.kind == MessageKind.COMMAND else False
        )

        response = None
        if not handled_command:
            thinking = h.language.get_response_prefix(language)["thinking"]
            reply(thinking)
            response = h.conversation.ask_trinity(text, language)
            reply(response)

        h.consciousness.save()
        self._complete(events, "command" if handled_command else "conversation")
        return response
