"""Scheduled briefing generation for Trinity."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class BriefingService:
    """Build and record the morning briefing outside the main brain class."""

    def __init__(self, host: Any, *, now: Callable[[], datetime] = datetime.now) -> None:
        self.host = host
        self.now = now


    def github_context(self) -> str:
        """Build live GitHub context for prompts and briefings."""
        try:
            github_skill = self.host.skills.get_skill("github")
            if not github_skill:
                return ""
            context = github_skill.get_all_repos_context()
            lines = ["LIVE GITHUB STATUS:"]
            for repo, data in context.items():
                lines.append(f"\n{repo}:")
                lines.append(f"  Files: {data['total_files']}")
                commits = data.get("recent_commits", [])
                if commits:
                    lines.append(f"  Last commit: {commits[0]['message'][:50]}")
                workflows = data.get("recent_workflows", [])
                failed = [w for w in workflows if w.get("conclusion") == "failure"]
                if failed:
                    lines.append(f"  FAILED workflows: {len(failed)}")
            return "\n".join(lines)
        except Exception as exc:
            return f"GitHub context error: {exc}"

    def business_summary(self) -> dict:
        """Return business status for the daily briefing."""
        try:
            business_skill = self.host.skills.get_skill("business")
            if not business_skill:
                return {}
            return business_skill.execute("get_business_status", {})
        except Exception:
            return {}

    def deliver_morning(self) -> str:
        h = self.host
        print("Preparing morning briefing...")
        h.consciousness.set_focus("Morning briefing")

        github_context = h.execute_skill_conscious(
            "github", "get_context", args={}, execute_fn=self.github_context
        )
        h.github_context_cache = github_context
        health = h.execute_skill_conscious(
            "health", "get_summary", args={}, execute_fn=h.status_service.health_summary
        )
        business = h.execute_skill_conscious(
            "business", "get_summary", args={}, execute_fn=self.business_summary
        )
        web_result = h.execute_skill_conscious(
            "web", "check_all_trinity6", args={},
            execute_fn=lambda: h.skills.execute("web", "check_all_trinity6", {}),
        )

        alerts: list[str] = []
        if not web_result.get("website_live", True):
            alerts.append("Website trinity6.com is DOWN")
            h.consciousness.remember(
                "trinity6.com is DOWN during morning briefing", "episodic",
                tags=["alert", "website", "downtime", "critical"],
                outcome="failure", importance=0.95,
            )
        if not health.get("website_live", True):
            alerts.append("Website health check failed")
        alerts.extend(business.get("alerts", []))

        github_skill = h.skills.get_skill("github")
        failed_workflows: list[str] = []
        if github_skill:
            for repo in ("Trinity6", "assistant", "trinity-ai"):
                runs = h.execute_skill_conscious(
                    "github", "get_workflow_runs", args={"repo": repo, "count": 3},
                    execute_fn=lambda r=repo: github_skill.get_workflow_runs(r, 3),
                )
                for run in runs.get("runs", []):
                    if run.get("conclusion") == "failure":
                        failed_workflows.append(f"{repo}: {run['name']}")
        if failed_workflows:
            h.consciousness.remember(
                f"Failed workflows detected: {', '.join(failed_workflows)}", "episodic",
                tags=["alert", "github", "workflow", "failure"],
                outcome="failure", importance=0.7,
            )

        days_alive = h.memory.get_days_alive()
        revenue = business.get("revenue", 0)
        clients = business.get("total_clients", 0)
        next_milestone = business.get("next_milestone", "First paying client")
        h.consciousness.learn(
            f"Current revenue: {revenue} INR, active clients: {clients}",
            tags=["business", "metrics"], confidence=0.95,
        )
        website_status = "online" if web_result.get("website_live") else "offline"
        briefing = f"""Good morning David!

Trinity6 Daily Briefing
{self.now().strftime('%A %B %d %Y')}

Company Status
Days building: {days_alive}
Revenue: {revenue} INR
Active clients: {clients}
Next milestone: {next_milestone}

Website: trinity6.com is {website_status}

GitHub Activity:
{github_context}"""
        if failed_workflows:
            briefing += "\n\nFailed Workflows:" + "".join(f"\n- {wf}" for wf in failed_workflows)
        if alerts:
            briefing += "\n\nAlerts:" + "".join(f"\n- {alert}" for alert in alerts)
        else:
            briefing += "\n\nAll systems healthy."
        briefing += "\n\nSend /help for commands or ask me anything."

        notifier = getattr(h, "notify", None)
        if callable(notifier):
            notifier(briefing, category="morning_briefing")
        else:
            h.respond(briefing)
        h.memory.add_daily_log(f"Morning briefing delivered. Alerts: {len(alerts)}")
        h.memory.brain["company"]["days_building"] = h.memory.brain["company"].get("days_building", 0) + 1
        h.memory.save()
        h.consciousness.remember(
            f"Morning briefing delivered. {len(alerts)} alerts. Revenue: {revenue} INR. "
            f"Clients: {clients}. Website: {website_status}. Failed workflows: {len(failed_workflows)}.",
            "episodic", tags=["briefing", "daily", "morning"],
            outcome="success", importance=0.6,
        )
        h.consciousness.save()
        print("Morning briefing delivered!")
        return briefing
