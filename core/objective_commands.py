"""Explicit user controls for durable Objective / Focus state.

Objectives represent David's declared intent. This command surface intentionally
does not infer objectives from ordinary conversation and does not execute work.
"""
from __future__ import annotations

from typing import Any


class ObjectiveCommandService:
    """Parse and execute explicit objective lifecycle commands."""

    HELP = """Objective Commands

/objectives - list open objectives
/objectives all - include completed/abandoned/superseded objectives
/objective add <title> - create an objective
/objective focus <id> - make an active/blocked objective the current focus
/objective clear-focus - clear current focus
/objective progress <id> <0-100> - update explicit progress
/objective pause <id> - pause an objective
/objective resume <id> - return an objective to active
/objective complete <id> - mark an objective completed
/objective abandon <id> - mark an objective abandoned"""

    def __init__(self, host: Any) -> None:
        self.host = host

    @property
    def memory(self):
        return self.host.memory

    def _respond(self, message: str) -> None:
        self.host.respond(message)

    def _publish(self, event_type: str, **payload: Any) -> None:
        events = getattr(self.host, "events", None)
        if events is not None:
            events.publish(event_type, **payload)

    def _resolve(self, reference: str) -> dict[str, Any]:
        ref = str(reference or "").strip().lower()
        if not ref:
            raise ValueError("Objective ID is required.")

        items = self.memory.list_objectives()
        exact = [
            item for item in items
            if str(item.get("id", "")).lower() == ref
        ]
        if exact:
            return exact[0]

        matches = [
            item for item in items
            if str(item.get("id", "")).lower().startswith(ref)
        ]
        if not matches:
            raise ValueError(f"No objective matches '{reference}'.")
        if len(matches) > 1:
            ids = ", ".join(str(item["id"])[:8] for item in matches[:5])
            raise ValueError(
                f"Objective ID '{reference}' is ambiguous. Matches: {ids}"
            )
        return matches[0]

    @staticmethod
    def _percent(value: Any) -> int:
        return int(round(float(value or 0.0) * 100))

    def _list(self, *, include_terminal: bool) -> None:
        items = self.memory.list_objectives()
        terminal = self.memory.TERMINAL_OBJECTIVE_STATUSES
        if not include_terminal:
            items = [
                item for item in items
                if item.get("status") not in terminal
            ]

        focus = self.memory.get_current_focus()
        focus_id = str(focus.get("id")) if focus else None

        if not items:
            message = (
                "No objectives yet.\n\n"
                "Create one with: /objective add <title>"
                if not include_terminal
                else "No objective history yet."
            )
            self._respond(message)
            return

        lines = ["Objectives"]
        if focus:
            lines.append(
                f"Current focus: {focus['title']} [{str(focus['id'])[:8]}]"
            )
        else:
            lines.append("Current focus: none")
        lines.append("")

        for item in items[:20]:
            marker = "FOCUS" if str(item.get("id")) == focus_id else "     "
            lines.append(
                f"{marker} {str(item.get('id', ''))[:8]} | "
                f"{item.get('status', 'unknown')} | "
                f"{self._percent(item.get('progress', 0.0))}% | "
                f"{item.get('title', '')}"
            )

        if len(items) > 20:
            lines.append(f"...and {len(items) - 20} more")

        self._respond("\n".join(lines))

    def _status_change(self, action: str, reference: str) -> None:
        objective = self._resolve(reference)
        status_map = {
            "pause": "paused",
            "resume": "active",
            "complete": "completed",
            "abandon": "abandoned",
        }
        status = status_map[action]
        updated = self.memory.set_objective_status(
            objective["id"],
            status,
            reason=f"{status} explicitly by David",
        )
        self._publish(
            "objective.user_status_changed",
            objective_id=updated["id"],
            status=status,
        )
        self._respond(
            f"Objective {status}: {updated['title']} "
            f"[{str(updated['id'])[:8]}]"
        )

    def handle(self, command: str) -> bool:
        raw = str(command or "").strip()
        if not raw:
            return False

        first, *tail = raw.split(maxsplit=1)
        root = first.lower()
        rest = tail[0].strip() if tail else ""

        if root == "/objectives":
            include_terminal = rest.lower() == "all"
            if rest and not include_terminal:
                self._respond("Usage: /objectives OR /objectives all")
                return True
            self._list(include_terminal=include_terminal)
            return True

        if root != "/objective":
            return False

        if not rest:
            self._respond(self.HELP)
            return True

        action_parts = rest.split(maxsplit=1)
        action = action_parts[0].lower()
        args = action_parts[1].strip() if len(action_parts) > 1 else ""

        try:
            if action == "add":
                if not args:
                    raise ValueError("Usage: /objective add <title>")
                objective = self.memory.create_objective(args)
                self._publish(
                    "objective.user_created",
                    objective_id=objective["id"],
                    title=objective["title"],
                )
                self._respond(
                    f"Objective created: {objective['title']} "
                    f"[{str(objective['id'])[:8]}]\n"
                    f"Set focus with: /objective focus {str(objective['id'])[:8]}"
                )
                return True

            if action == "focus":
                objective = self._resolve(args)
                focused = self.memory.set_current_focus(objective["id"])
                self._publish(
                    "objective.user_focus_changed",
                    objective_id=focused["id"],
                )
                self._respond(
                    f"Current focus: {focused['title']} "
                    f"[{str(focused['id'])[:8]}]"
                )
                return True

            if action == "clear-focus":
                if args:
                    raise ValueError("Usage: /objective clear-focus")
                previous = self.memory.get_current_focus()
                self.memory.set_current_focus(None)
                self._publish(
                    "objective.user_focus_changed",
                    objective_id=None,
                    previous_objective_id=(
                        previous.get("id") if previous else None
                    ),
                )
                self._respond("Current objective focus cleared.")
                return True

            if action == "progress":
                progress_parts = args.split(maxsplit=1)
                if len(progress_parts) != 2:
                    raise ValueError(
                        "Usage: /objective progress <id> <0-100>"
                    )
                objective = self._resolve(progress_parts[0])
                try:
                    percent = float(progress_parts[1])
                except ValueError as exc:
                    raise ValueError(
                        "Progress must be a number from 0 to 100."
                    ) from exc
                if not 0.0 <= percent <= 100.0:
                    raise ValueError(
                        "Progress must be a number from 0 to 100."
                    )
                updated = self.memory.update_objective_progress(
                    objective["id"],
                    percent / 100.0,
                )
                self._publish(
                    "objective.user_progress_updated",
                    objective_id=updated["id"],
                    progress=updated["progress"],
                )
                self._respond(
                    f"Objective progress: {updated['title']} — "
                    f"{self._percent(updated['progress'])}%"
                )
                return True

            if action in {"pause", "resume", "complete", "abandon"}:
                if not args:
                    raise ValueError(
                        f"Usage: /objective {action} <id>"
                    )
                self._status_change(action, args)
                return True

            self._respond(self.HELP)
            return True

        except (KeyError, ValueError, RuntimeError) as exc:
            self._respond(str(exc))
            return True
