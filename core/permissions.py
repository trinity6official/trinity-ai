"""Central permission policy for Trinity actions and tools."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PermissionLevel(str, Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    HIGH_RISK = "high_risk"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class PermissionDecision:
    level: PermissionLevel
    reason: str

    @property
    def allowed_autonomously(self) -> bool:
        return self.level == PermissionLevel.SAFE

    @property
    def requires_confirmation(self) -> bool:
        return self.level in {PermissionLevel.CONFIRM, PermissionLevel.HIGH_RISK}


class PermissionEngine:
    """Policy engine for autonomous vs. approval-gated behavior."""

    SAFE_ACTIONS = {
        "daily_content_posting",
        "morning_briefing",
        "evening_checkin",
        "monitoring_checks",
        "alert_sending",
        "memory_updates",
        "self_improvement",
        "health_checks",
        "weekly_report",
        "content_generation",
    }

    CONFIRM_ACTIONS = {
        "spending_money",
        "contacting_clients",
        "major_product_changes",
        "deleting_files",
        "sending_external_emails",
        "publishing_to_website",
        "anything_uncertain",
        "network_scanning",
        "restore_memory",
    }

    FORBIDDEN_ACTIONS = {
        "spend_money_without_approval",
        "contact_external_people_alone",
        "make_irreversible_changes",
        "ignore_davids_wellbeing",
        "delete_critical_files",
        "share_private_information",
    }

    READ_PREFIXES = (
        "get_", "read_", "list_", "check_", "search_", "find_", "review_",
        "analyze_", "audit_", "calculate", "compare_",
    )
    CONFIRM_PREFIXES = (
        "create_", "update_", "delete_", "revert_", "publish_", "send_", "contact_",
    )
    HIGH_RISK_PREFIXES = (
        "shell_", "execute_shell", "run_command", "production_", "rotate_secret", "change_firewall",
    )

    TOOL_OVERRIDES = {
        "github.self_commit_improvement": PermissionLevel.CONFIRM,
        # Local-only computer observation is safe; desktop mutation still requires approval.
        "computer.list_directory": PermissionLevel.SAFE,
        "computer.read_text": PermissionLevel.SAFE,
        "computer.frontmost_app": PermissionLevel.SAFE,
        "computer.list_running_apps": PermissionLevel.SAFE,
        "computer.capture_screen": PermissionLevel.SAFE,
        "computer.open_app": PermissionLevel.CONFIRM,
        "computer.activate_app": PermissionLevel.CONFIRM,
        "computer.type_text": PermissionLevel.CONFIRM,
        "computer.click": PermissionLevel.CONFIRM,
        "computer.run_command": PermissionLevel.HIGH_RISK,
    }

    def assess_action(self, action: str) -> PermissionDecision:
        action = (action or "").strip().lower()
        if action in self.FORBIDDEN_ACTIONS:
            return PermissionDecision(PermissionLevel.FORBIDDEN, "Action is explicitly forbidden")
        if action in self.CONFIRM_ACTIONS:
            return PermissionDecision(PermissionLevel.CONFIRM, "Explicit user approval is required")
        if action in self.SAFE_ACTIONS:
            return PermissionDecision(PermissionLevel.SAFE, "Action is approved for autonomous execution")
        return PermissionDecision(PermissionLevel.CONFIRM, "Unknown action defaults to confirmation")

    def assess_tool(self, skill: str, tool: str) -> PermissionDecision:
        """Classify a tool call conservatively from its name.

        This is the default policy. Skills may later register stricter explicit rules.
        """
        name = (tool or "").strip().lower()
        qualified = f"{(skill or '').strip().lower()}.{name}"
        override = self.TOOL_OVERRIDES.get(qualified)
        if override is not None:
            return PermissionDecision(override, f"Explicit tool policy: {qualified}")

        if name.startswith(self.HIGH_RISK_PREFIXES):
            return PermissionDecision(PermissionLevel.HIGH_RISK, f"High-risk tool: {qualified}")
        if name.startswith(self.CONFIRM_PREFIXES):
            return PermissionDecision(PermissionLevel.CONFIRM, f"Mutating/external tool: {qualified}")
        if name.startswith(self.READ_PREFIXES):
            return PermissionDecision(PermissionLevel.SAFE, f"Read/analysis tool: {qualified}")
        return PermissionDecision(PermissionLevel.CONFIRM, f"Unclassified tool defaults to confirmation: {qualified}")
