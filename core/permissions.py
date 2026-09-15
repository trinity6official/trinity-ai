"""Central permission policy for Trinity actions and tools."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.trust_context import TrustContext, TrustLevel, get_current_trust_context


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

    @staticmethod
    def _apply_trust(
        decision: PermissionDecision,
        context: TrustContext | None,
    ) -> PermissionDecision:
        """Raise the approval bar for unverified request sources.

        Lock state deliberately does not change permissions.  A trusted local
        request stays trusted while the display is locked, and an authenticated
        remote request remains usable.  What changes policy is request trust.
        """
        context = context or get_current_trust_context()
        if context.level != TrustLevel.UNVERIFIED:
            return decision

        if decision.level == PermissionLevel.SAFE:
            return PermissionDecision(
                PermissionLevel.CONFIRM,
                f"Unverified source requires approval: {decision.reason}",
            )
        if decision.level == PermissionLevel.CONFIRM:
            return PermissionDecision(
                PermissionLevel.HIGH_RISK,
                f"Unverified source requires stronger approval: {decision.reason}",
            )
        return decision

    def assess_action(
        self,
        action: str,
        context: TrustContext | None = None,
    ) -> PermissionDecision:
        action = (action or "").strip().lower()
        if action in self.FORBIDDEN_ACTIONS:
            decision = PermissionDecision(PermissionLevel.FORBIDDEN, "Action is explicitly forbidden")
        elif action in self.CONFIRM_ACTIONS:
            decision = PermissionDecision(PermissionLevel.CONFIRM, "Explicit user approval is required")
        elif action in self.SAFE_ACTIONS:
            decision = PermissionDecision(PermissionLevel.SAFE, "Action is approved for autonomous execution")
        else:
            decision = PermissionDecision(PermissionLevel.CONFIRM, "Unknown action defaults to confirmation")
        return self._apply_trust(decision, context)

    def assess_tool(
        self,
        skill: str,
        tool: str,
        context: TrustContext | None = None,
    ) -> PermissionDecision:
        """Classify a tool call conservatively, then apply request trust."""
        name = (tool or "").strip().lower()
        qualified = f"{(skill or '').strip().lower()}.{name}"
        override = self.TOOL_OVERRIDES.get(qualified)
        if override is not None:
            decision = PermissionDecision(override, f"Explicit tool policy: {qualified}")
        elif name.startswith(self.HIGH_RISK_PREFIXES):
            decision = PermissionDecision(PermissionLevel.HIGH_RISK, f"High-risk tool: {qualified}")
        elif name.startswith(self.CONFIRM_PREFIXES):
            decision = PermissionDecision(PermissionLevel.CONFIRM, f"Mutating/external tool: {qualified}")
        elif name.startswith(self.READ_PREFIXES):
            decision = PermissionDecision(PermissionLevel.SAFE, f"Read/analysis tool: {qualified}")
        else:
            decision = PermissionDecision(
                PermissionLevel.CONFIRM,
                f"Unclassified tool defaults to confirmation: {qualified}",
            )
        return self._apply_trust(decision, context)
