"""Slash-command execution for Trinity's user interfaces."""
from __future__ import annotations

from core.objective_commands import ObjectiveCommandService


class CommandHandler:
    """Host adapter that keeps command-specific behavior out of Trinity's main brain."""

    COMMANDS = {
        "/start", "/help", "/briefing", "/progress", "/next", "/business",
        "/security", "/client", "/status", "/brain", "/pending",
        "/objective", "/objectives",
    }

    def __init__(self, trinity) -> None:
        self.trinity = trinity
        self.objectives = ObjectiveCommandService(trinity)

    def _execution_context(self) -> dict[str, str]:
        focus = self.trinity.memory.get_current_focus()
        if not focus:
            return {}
        return {
            "objective_id": str(focus["id"]),
            "objective_title": str(focus.get("title", "")),
        }

    def _execute_skill(self, skill: str, tool: str, params=None):
        t = self.trinity
        args = dict(params or {})
        context = self._execution_context()
        return t.execute_skill_conscious(
            skill,
            tool,
            args=args,
            execute_fn=lambda: t.skills.execute(
                skill,
                tool,
                args,
                context=context,
            ),
        )

    def handle(self, command: str, language: str = "english") -> bool:
        t = self.trinity
        raw_command = str(command or "").strip()
        if not raw_command:
            return False
        command = raw_command.split(maxsplit=1)[0].lower()
        if command not in self.COMMANDS:
            return False
        if command in {"/objective", "/objectives"}:
            return self.objectives.handle(raw_command)

        if command in {"/start", "/help"}:
            t.response_processor.reset_skill_failures()
            t.status_service.send_help(language)
            return True

        if command == "/briefing":
            t.response_processor.reset_skill_failures()
            t.respond("Preparing your briefing...")
            t.briefings.deliver_morning()
            return True

        if command == "/progress":
            t.respond("Reading repositories...")
            context = self._execute_skill(
                "github",
                "get_all_repos_context",
            )
            msg = "Repository Progress\n\n"
            for repo, data in context.items():
                msg += f"{repo}\n"
                msg += f"  Files: {data['total_files']}\n"
                commits = data.get("recent_commits", [])
                if commits:
                    msg += f"  Last commit: {commits[0]['message'][:50]}\n"
                msg += "\n"
            t.respond(msg)
            return True

        if command == "/next":
            result = self._execute_skill(
                "business",
                "get_weekly_priorities",
            )
            msg = "Weekly Priorities\n\n"
            for p in result.get("priorities", []):
                msg += f"{p['priority']}. {p['action']}\n"
                msg += f"   Why: {p['why']}\n"
                msg += f"   How: {p['how']}\n\n"
            t.respond(msg)
            return True

        if command == "/business":
            result = self._execute_skill(
                "business",
                "get_business_status",
            )
            msg = f"""Business Status

Health Score: {result.get('health_score', 0)}/100
Revenue: {result.get('revenue', 0)} INR
Active Clients: {result.get('total_clients', 0)}
Prospects: {result.get('total_prospects', 0)}
Days Building: {result.get('days_building', 0)}
Next Milestone: {result.get('next_milestone', '')}"""
            alerts = result.get("alerts", [])
            if alerts:
                msg += "\n\nAlerts:"
                for alert in alerts:
                    msg += f"\n- {alert}"
            t.respond(msg)
            return True

        if command == "/security":
            t.respond("Running security check...")
            result = self._execute_skill(
                "web",
                "check_all_trinity6",
            )
            alerts = result.get("alerts", [])
            msg = f"""Security Check

Website: {'Online' if result.get('website_live') else 'Offline'}
Overall: {result.get('overall', 'unknown').upper()}"""
            if alerts:
                msg += "\n\nAlerts:"
                for alert in alerts:
                    msg += f"\n- {alert}"
            else:
                msg += "\n\nNo issues detected."
            t.respond(msg)
            t.consciousness.remember(
                f"Security check: {'Online' if result.get('website_live') else 'OFFLINE'}. Alerts: {len(alerts)}.",
                "episodic",
                tags=["security", "check"],
                outcome="success" if not alerts else "partial",
                importance=0.5 if not alerts else 0.8,
            )
            return True

        if command == "/client":
            pipeline = self._execute_skill(
                "business",
                "get_client_pipeline",
            )
            outreach = self._execute_skill(
                "business",
                "plan_outreach",
                {"target_count": 10},
            )
            summary = pipeline.get("summary", {})
            msg = (
                "Client Strategy\n\n"
                f"Pipeline: {pipeline.get('total_in_pipeline', 0)} total\n"
                f"Prospects: {summary.get('prospects', 0)}\n"
                f"In discussion: {summary.get('in_discussion', 0)}\n"
                f"Active clients: {summary.get('active', 0)}\n\n"
                f"Weekly outreach target: {outreach.get('weekly_target', 0)}\n"
            )
            plan = outreach.get("plan", [])
            if plan:
                first_day = plan[0]
                msg += f"Next outreach block: {first_day.get('day', '')}\n"
                for action in first_day.get("actions", [])[:3]:
                    msg += f"- {action}\n"
            template = outreach.get("templates", {}).get(
                "connection_request",
                "",
            )
            if template:
                msg += f"\nConnection template:\n{template}"
            t.respond(msg)
            return True

        if command == "/status":
            t.status_service.send_status()
            return True

        if command == "/brain":
            t.status_service.send_brain_status()
            return True

        if command == "/pending":
            pending = t.skills.get_pending_changes()
            evolution = getattr(t, "skill_evolution", None)
            evolution_pending = evolution.get_pending_changes() if evolution is not None else {}
            get_pending_actions = getattr(t.skills, "get_pending_actions", None)
            action_pending = get_pending_actions() if callable(get_pending_actions) else {}
            if not isinstance(action_pending, dict):
                action_pending = {}
            mcp_execution = getattr(t, "mcp_execution", None)
            mcp_pending = mcp_execution.get_pending_actions() if mcp_execution is not None else {}

            sections = []
            for change_id, change in pending.items():
                sections.append(
                    "GitHub change\n"
                    f"ID: {change_id}\n"
                    f"Repo: {change.get('repo', '')}\n"
                    f"File: {change.get('path', '')}\n"
                    f"Reason: {change.get('reason', '')}"
                )
            for proposal in evolution_pending.values():
                sections.append(
                    "Trinity skill improvement\n"
                    f"Proposal: {proposal.get('id', '')}\n"
                    f"File: {proposal.get('path', '')}\n"
                    f"Reason: {proposal.get('reason', '')}\n"
                    "Exact diff under review:\n"
                    f"{proposal.get('review', '(review unavailable)')}"
                )
            for approval_id, action in action_pending.items():
                sections.append(
                    "Pending action\n"
                    f"ID: {approval_id}\n"
                    f"Action: {action.get('skill', '')}.{action.get('tool', '')}\n"
                    f"Params: {action.get('params', {})}"
                )
            for approval_id, action in mcp_pending.items():
                sections.append(
                    "Pending MCP action\n"
                    f"ID: {approval_id}\n"
                    f"Action: {action.get('server', '')}.{action.get('tool', '')}\n"
                    f"Arguments: {action.get('arguments', {})}"
                )

            if sections:
                msg = (
                    "Pending changes waiting for approval:\n\n"
                    + "\n\n".join(sections)
                    + "\n\n"
                    + (
                        "Reply YES to approve it or NO to cancel it. "
                        "You can also use APPROVE <id> or REJECT <id>."
                        if len(sections) == 1
                        else "Multiple approvals are pending. "
                        "Reply APPROVE <id> or REJECT <id>."
                    )
                )
            else:
                msg = "No pending changes."
            t.respond(msg)
            return True

        return False
