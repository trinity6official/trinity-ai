"""Unified agent execution runtime for Trinity."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping
from uuid import uuid4

from core.permissions import PermissionDecision, PermissionEngine, PermissionLevel
from core.audit import ActionAuditTrail
from core.execution import ApprovalTicket, AgentExecutionRequest, freeze_mapping, thaw_mapping
from core.trust_context import get_current_trust_context


@dataclass(frozen=True)
class AgentContext:
    """Immutable handler context constructed inside the registry boundary."""

    objective: str
    data: Mapping[str, Any] = field(default_factory=dict)
    approved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective", str(self.objective))
        object.__setattr__(self, "data", freeze_mapping(self.data))


@dataclass(frozen=True)
class AgentResult:
    success: bool
    output: Any = None
    error: str | None = None
    requires_approval: bool = False
    permission: PermissionLevel | None = None
    approval_id: str | None = None


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
        self._pending_actions: dict[str, ApprovalTicket] = {}

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

    def get_pending_actions(self) -> dict[str, dict[str, Any]]:
        result = {}
        for approval_id, ticket in self._pending_actions.items():
            item = ticket.request.as_pending_action(
                approval_id, ticket.permission
            )
            if ticket.action_id:
                item["action_id"] = ticket.action_id
            result[approval_id] = item
        return result

    def execute(self, name: str, context: AgentContext) -> AgentResult:
        """Compatibility wrapper around the explicit agent request boundary."""
        if context.approved:
            error = (
                "Caller-supplied approval is not accepted; "
                "request the agent action first and approve its pending ID"
            )
            spec = self._agents.get(name.strip().lower())
            permission = (
                self.permissions.assess_action(spec.action_type).level
                if spec is not None else None
            )
            if self.audit_trail is not None:
                action_id = self.audit_trail.record(
                    actor_type="agent",
                    action=name.strip().lower(),
                    status="requested",
                    permission=permission.value if permission else None,
                    approved=False,
                    params={
                        "objective": context.objective,
                        "data": thaw_mapping(context.data),
                    },
                    metadata={"caller_supplied_approval": True},
                )
                self.audit_trail.record(
                    actor_type="agent",
                    action=name.strip().lower(),
                    status="denied",
                    action_id=action_id,
                    permission=permission.value if permission else None,
                    approved=False,
                    error=error,
                    metadata={"caller_supplied_approval": True},
                )
            return AgentResult(False, error=error, permission=permission)
        return self.execute_request(
            AgentExecutionRequest(
                agent=name,
                objective=context.objective,
                data=context.data,
            )
        )

    def execute_request(self, request: AgentExecutionRequest) -> AgentResult:
        """Execute a caller-created immutable agent request without approval privilege."""
        return self._execute_request(request)

    def _execute_request(
        self,
        request: AgentExecutionRequest,
        *,
        approval_granted: bool = False,
        action_id: str | None = None,
        permission: str | None = None,
        approval_id: str | None = None,
    ) -> AgentResult:
        key = request.agent
        context = AgentContext(
            request.objective,
            data=request.data,
            approved=bool(approval_granted),
        )
        spec = self._agents.get(key)
        if spec is None:
            if self.audit_trail is not None:
                if not approval_granted:
                    action_id = self.audit_trail.record(
                        actor_type="agent", action=key or request.agent,
                        status="requested", approved=False,
                        params={
                            "objective": context.objective,
                            "data": thaw_mapping(context.data),
                        },
                    )
                self.audit_trail.record(
                    actor_type="agent", action=key or request.agent,
                    status="failed", action_id=action_id,
                    approved=bool(approval_granted),
                    error=f"Unknown agent: {request.agent}",
                )
            return AgentResult(False, error=f"Unknown agent: {request.agent}")

        allowed = spec.contract.allowed_data_keys
        if allowed is not None:
            unexpected = sorted(set(context.data) - set(allowed))
            if unexpected:
                error = "Agent input violates contract: " + ", ".join(unexpected)
                if self.audit_trail is not None:
                    if not approval_granted:
                        action_id = self.audit_trail.record(
                            actor_type="agent", action=key, status="requested",
                            approved=False,
                            params={
                                "objective": context.objective,
                                "data": thaw_mapping(context.data),
                            },
                            metadata={"contract_violation": True},
                        )
                    self.audit_trail.record(
                        actor_type="agent", action=key, status="denied",
                        action_id=action_id, approved=bool(approval_granted),
                        error=error,
                    )
                return AgentResult(False, error=error)

        decision = self.permissions.assess_action(spec.action_type)
        audit_permission = permission or decision.level.value
        if self.audit_trail is not None and not approval_granted:
            action_id = self.audit_trail.record(
                actor_type="agent", action=key, status="requested",
                permission=audit_permission, approved=False,
                params={
                    "objective": context.objective,
                    "data": thaw_mapping(context.data),
                },
                metadata={"action_type": spec.action_type},
            )

        if decision.level == PermissionLevel.FORBIDDEN:
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="denied",
                    action_id=action_id, permission=audit_permission,
                    approved=bool(approval_granted), error=decision.reason,
                )
            return AgentResult(False, error=decision.reason, permission=decision.level)

        if decision.requires_confirmation and not approval_granted:
            approval_id = uuid4().hex[:12]
            self._pending_actions[approval_id] = ApprovalTicket(
                request=request,
                action_id=action_id,
                permission=decision.level.value,
            )
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="approval_required",
                    action_id=action_id, permission=audit_permission,
                    approved=False, error=decision.reason,
                    metadata={
                        "action_type": spec.action_type,
                        "approval_id": approval_id,
                    },
                )
            return AgentResult(
                False,
                error=decision.reason,
                requires_approval=True,
                permission=decision.level,
                approval_id=approval_id,
            )

        if self.audit_trail is not None:
            if approval_granted:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="approved",
                    action_id=action_id, permission=audit_permission,
                    approved=True,
                    metadata={"approval_id": approval_id} if approval_id else None,
                )
            self.audit_trail.record(
                actor_type="agent", action=key, status="started",
                action_id=action_id, permission=audit_permission,
                approved=bool(approval_granted),
            )

        try:
            output = spec.handler(context)
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="completed",
                    action_id=action_id, permission=audit_permission,
                    approved=bool(approval_granted), result=output,
                )
            return AgentResult(True, output=output, permission=decision.level)
        except Exception as exc:
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="agent", action=key, status="failed",
                    action_id=action_id, permission=audit_permission,
                    approved=bool(approval_granted), error=str(exc),
                )
            return AgentResult(False, error=str(exc), permission=decision.level)

    def approve_action(self, approval_id: str) -> AgentResult:
        if not get_current_trust_context().can_approve:
            return AgentResult(
                False,
                error="Owner verification is required to approve this agent action",
            )
        approval_id = str(approval_id)
        ticket = self._pending_actions.pop(approval_id, None)
        if ticket is None:
            return AgentResult(False, error="Pending agent action not found")
        return self._execute_request(
            ticket.request,
            approval_granted=True,
            action_id=ticket.action_id,
            permission=ticket.permission,
            approval_id=approval_id,
        )

    def cancel_action(self, approval_id: str) -> bool:
        if not get_current_trust_context().can_approve:
            return False
        approval_id = str(approval_id)
        ticket = self._pending_actions.pop(approval_id, None)
        if ticket is None:
            return False
        if self.audit_trail is not None:
            self.audit_trail.record(
                actor_type="agent",
                action=ticket.request.action,
                status="denied",
                action_id=ticket.action_id,
                permission=ticket.permission,
                approved=False,
                params={
                    "objective": ticket.request.objective,
                    "data": thaw_mapping(ticket.request.data),
                },
                error="Pending agent action cancelled by user",
                metadata={"approval_id": approval_id},
            )
        return True
