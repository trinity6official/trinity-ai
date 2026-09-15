"""Slash-command execution for Trinity's chat interface."""
from __future__ import annotations


class CommandHandler:
    """Host adapter that keeps command-specific behavior out of Trinity's main brain."""

    COMMANDS = {
        "/start", "/help", "/briefing", "/progress", "/next", "/business",
        "/security", "/client", "/status", "/brain", "/pending",
    }

    def __init__(self, trinity) -> None:
        self.trinity = trinity

    def handle(self, command: str, language: str = "english") -> bool:
        t = self.trinity
        command = command.lower()
        if command not in self.COMMANDS:
            return False

        if command in {"/start", "/help"}:
            t.reset_skill_failures()
            t.send_help(language)
            return True

        if command == "/briefing":
            t.reset_skill_failures()
            t.send_telegram("Preparing your briefing...")
            t.deliver_morning_briefing()
            return True

        if command == "/progress":
            t.send_telegram("Reading repositories...")
            github_skill = t.skills.get_skill("github")
            if github_skill:
                context = t.execute_skill_conscious(
                    "github",
                    "get_all_repos_context",
                    args={},
                    execute_fn=lambda: github_skill.get_all_repos_context(),
                )
                msg = "Repository Progress\n\n"
                for repo, data in context.items():
                    msg += f"{repo}\n"
                    msg += f"  Files: {data['total_files']}\n"
                    commits = data.get("recent_commits", [])
                    if commits:
                        msg += f"  Last commit: {commits[0]['message'][:50]}\n"
                    msg += "\n"
                t.send_telegram(msg)
            return True

        if command == "/next":
            result = t.execute_skill_conscious(
                "business",
                "get_weekly_priorities",
                args={},
                execute_fn=lambda: t.skills.execute("business", "get_weekly_priorities", {}),
            )
            msg = "Weekly Priorities\n\n"
            for p in result.get("priorities", []):
                msg += f"{p['priority']}. {p['action']}\n"
                msg += f"   Why: {p['why']}\n"
                msg += f"   How: {p['how']}\n\n"
            t.send_telegram(msg)
            return True

        if command == "/business":
            result = t.execute_skill_conscious(
                "business",
                "get_business_status",
                args={},
                execute_fn=lambda: t.skills.execute("business", "get_business_status", {}),
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
            t.send_telegram(msg)
            return True

        if command == "/security":
            t.send_telegram("Running security check...")
            result = t.execute_skill_conscious(
                "web",
                "check_all_trinity6",
                args={},
                execute_fn=lambda: t.skills.execute("web", "check_all_trinity6", {}),
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
            t.send_telegram(msg)
            t.consciousness.remember(
                f"Security check: {'Online' if result.get('website_live') else 'OFFLINE'}. Alerts: {len(alerts)}.",
                "episodic",
                tags=["security", "check"],
                outcome="success" if not alerts else "partial",
                importance=0.5 if not alerts else 0.8,
            )
            return True

        if command == "/client":
            result = t.execute_skill_conscious(
                "business",
                "find_potential_clients",
                args={"location": "Chennai", "industry": "any"},
                execute_fn=lambda: t.skills.execute(
                    "business", "find_potential_clients", {"location": "Chennai", "industry": "any"}
                ),
            )
            msg = "First Client Strategy\n\nTarget Industries:\n"
            for ind in result.get("industries_to_target", [])[:5]:
                msg += f"- {ind}\n"
            msg += "\nLinkedIn Searches:\n"
            for search in result.get("linkedin_searches", [])[:3]:
                msg += f"- {search}\n"
            msg += f"\nOutreach Message:\n{result.get('outreach_message', '')}"
            t.send_telegram(msg)
            return True

        if command == "/status":
            t.send_status()
            return True

        if command == "/brain":
            t._send_brain_status()
            return True

        if command == "/pending":
            pending = t.skills.get_pending_changes()
            if pending:
                msg = "Pending changes waiting for approval:\n\n"
                for change in pending.values():
                    msg += f"Repo: {change.get('repo', '')}\n"
                    msg += f"File: {change.get('path', '')}\n"
                    msg += f"Reason: {change.get('reason', '')}\n"
                    msg += "Reply YES to approve or NO to cancel\n\n"
            else:
                msg = "No pending changes."
            t.send_telegram(msg)
            return True

        return False
