"""Unified agent execution runtime for Trinity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core.permissions import PermissionDecision, PermissionEngine, PermissionLevel
from core.audit import ActionAuditTrail


@dataclass(frozen=True)
class AgentContext:
    objective: str
    data: dict[str, Any] = field(default_factory=dict)
    approved: bool = False


@dataclass(frozen=True)
class AgentResult:
    success: bool
    output: Any = None
    error: str | None = None
    requires_approval: bool = False
    permission: PermissionLevel | None = None


AgentHandler = Callable[[AgentContext], Any]


@dataclass(frozen=True)
class AgentContract:
    """Explicit execution contract for a registered agent capability."""
    allowed_data_keys: tuple[str, ...] | None = None
    network_access: bool = False
    memory_access: str = "none"
    side_effects: str = "none"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    handler: AgentHandler
    action_type: str
    description: str = ""
    contract: AgentContract = field(default_factory=AgentContract)


class AgentRegistry:
    """Registers agents and executes them through the central permission policy."""

    def __init__(
        self, permissions: PermissionEngine | None = None,
        audit_trail: ActionAuditTrail | None = None,
    ) -> None:
        self.permissions = permissions or PermissionEngine()
        self.audit_trail = audit_trail
        self._agents: dict[str, AgentSpec] = {}

    def register(
        self,
        name: str,
        handler: AgentHandler,
        *,
        action_type: str,
        description: str = "",
        contract: AgentContract | None = None,
    ) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("Agent name cannot be empty")
        if key in self._agents:
            raise ValueError(f"Agent already registered: {key}")
        self._agents[key] = AgentSpec(
            key, handler, action_type, description, contract or AgentContract()
        )

    def names(self) -> list[str]:
        return sorted(self._agents)

    def describe(self, name: str) -> AgentSpec:
        """Return the immutable registered contract for introspection/UI use."""
        return self._agents[name.strip().lower()]

    def permission_for(self, name: str) -> PermissionDecision:
        spec = self._agents[name.strip().lower()]
        return self.permissions.assess_action(spec.action_type)

    def execute(self, name: str, context: AgentContext) -> AgentResult:
        key = name.strip().lower()
        spec = self._agents.get(key)
        action_id = None
        if spec is None:
            if self.audit_trail is not None:
                action_id = self.audit_trail.record(
                    actor_type="agent", action=key or name,
                    status="requested", approved=context.approved,
                    params={"objective": context.objective, "data": context.data},
                )
                self.audit_trail.record(
                    actor_type="agent", action=key or name,
                    status="failed", action_id=action_id,
                    approved=context.approved, error=f"Unknown agent: {name}",
                )
            return AgentResult(False, error=f"Unknown agent: {name}")

        allowed = spec.contract.allowed_data_keys
        if allowed is not None:
            unexpected = sorted(set(context.data) - set(allowed))
            if unexpected:
                error = "Agent input violates contract: " + ", ".join(unexpected)
                if self.audit_trail is not None:
                    action_id = self.audit_trail.record(
                        actor_type="agent", action=key, status="requested",
                        approved=context.approved,
                        params={"objective": context.objective, "data": context.data},
                        metadata={"contract_violation": True},
                    )
                    self.audit_trail.record(
                        actor_type="agent", action=key, status="denied",
                        action_id=action_id, approved=context.approved, error=error,
                    )
                return AgentResult(False, error=error)

        decision = self.permissions.assess_action(spec.action_type)
        if self.audit_trail is not None:
            action_id = self.audit_trail.record(
                actor_type="agent", action=key, status="requested",
                permission=decision.level.value, approved=context.approved,
                params={"objective": context.objective, "data": context.data},
                metadata={"action_type": spec.action_type},
            )

        if decision.level == PermissionLevel.FORBIDDEN:
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="denied",
                    action_id=action_id, permission=decision.level.value,
                    approved=context.approved, error=decision.reason,
                )
            return AgentResult(False, error=decision.reason, permission=decision.level)

        if decision.requires_confirmation and not context.approved:
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="approval_required",
                    action_id=action_id, permission=decision.level.value,
                    approved=False, error=decision.reason,
                )
            return AgentResult(
                False, error=decision.reason, requires_approval=True,
                permission=decision.level,
            )

        if self.audit_trail is not None:
            if context.approved and decision.requires_confirmation:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="approved",
                    action_id=action_id, permission=decision.level.value,
                    approved=True,
                )
            self.audit_trail.record(
                actor_type="agent", action=key, status="started",
                action_id=action_id, permission=decision.level.value,
                approved=context.approved,
            )

        try:
            output = spec.handler(context)
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="completed",
                    action_id=action_id, permission=decision.level.value,
                    approved=context.approved, result=output,
                )
            return AgentResult(True, output=output, permission=decision.level)
        except Exception as exc:
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="failed",
                    action_id=action_id, permission=decision.level.value,
                    approved=context.approved, error=str(exc),
                )
            return AgentResult(False, error=str(exc), permission=decision.level)

