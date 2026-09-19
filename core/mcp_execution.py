"""Governed MCP tool execution boundary.

MCPServerManager owns protocol transport. CapabilityRegistry owns discovery
metadata. This service is the only application-layer owner allowed to invoke
MCP tools and therefore centralizes allowlisting, permission/approval policy,
result limits and the shared action audit trail.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping
from uuid import uuid4

from core.execution import ApprovalTicket, MCPExecutionRequest, TaskExecutionResult, thaw_mapping
from core.permissions import PermissionLevel
from core.trust_context import get_current_trust_context


_MCP_CALL_RE = re.compile(r"MCP_CALL\s*:\s*([A-Za-z0-9_-]+)\.([A-Za-z0-9_.:/-]+)", re.I)


class MCPExecutionService:
    def __init__(self, host: Any) -> None:
        self.host = host
        self._pending_actions: dict[str, ApprovalTicket] = {}

    def get_pending_actions(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for approval_id, ticket in self._pending_actions.items():
            request = ticket.request
            result[approval_id] = request.as_pending_action(
                approval_id, ticket.permission
            )
            if ticket.action_id:
                result[approval_id]["action_id"] = ticket.action_id
        return result

    def execute(
        self,
        server: str,
        tool: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        context: Mapping[str, Any] | None = None,
    ):
        return self.execute_request(
            MCPExecutionRequest(
                server,
                tool,
                arguments or {},
                context=context or {},
            )
        )

    def execute_request(self, request: MCPExecutionRequest):
        try:
            config = self.host.mcp.config(request.server)
        except KeyError as exc:
            return self._denied(request, str(exc))
        decision = self.host.permissions.assess_mcp_tool(
            request.server, request.tool, server_trust=config.trust
        )
        args = thaw_mapping(request.arguments)
        action_id = self._audit(
            request, "requested", permission=decision.level.value, approved=False, params=args
        )
        denial = self._preflight(request, config, decision)
        if denial:
            self._audit(
                request, "denied", action_id=action_id,
                permission=decision.level.value, approved=False, params=args, error=denial,
            )
            return self._error(request, denial, permission_denied=True)

        if decision.requires_confirmation:
            approval_id = uuid4().hex[:12]
            self._pending_actions[approval_id] = ApprovalTicket(
                request=request,
                action_id=action_id,
                permission=decision.level.value,
            )
            self._audit(
                request, "approval_required", action_id=action_id,
                permission=decision.level.value, approved=False, params=args,
                metadata={"approval_id": approval_id},
            )
            return {
                "success": False,
                "error": decision.reason,
                "needs_approval": True,
                "approval_id": approval_id,
                "permission": decision.level.value,
                "server": request.server,
                "tool": request.tool,
            }
        return self._invoke(request, config, decision, action_id=action_id, approved=False)

    def approve_action(self, approval_id: str):
        if not get_current_trust_context().can_approve:
            return {
                "success": False,
                "error": "Owner verification is required to approve this MCP action",
                "permission_denied": True,
            }
        approval_id = str(approval_id)
        ticket = self._pending_actions.pop(approval_id, None)
        if ticket is None:
            return {"success": False, "error": "MCP approval not found"}
        request = ticket.request
        config = self.host.mcp.config(request.server)
        decision = self.host.permissions.assess_mcp_tool(
            request.server, request.tool, server_trust=config.trust
        )
        denial = self._preflight(request, config, decision)
        if denial:
            self._audit(
                request,
                "denied",
                action_id=ticket.action_id,
                permission=ticket.permission,
                approved=False,
                params=thaw_mapping(request.arguments),
                error=denial,
                metadata={"approval_id": approval_id},
            )
            return self._error(request, denial, permission_denied=True)
        self._audit(
            request,
            "approved",
            action_id=ticket.action_id,
            permission=ticket.permission,
            approved=True,
            params=thaw_mapping(request.arguments),
            metadata={"approval_id": approval_id},
        )
        return self._invoke(
            request,
            config,
            decision,
            action_id=ticket.action_id,
            approved=True,
        )

    def cancel_action(self, approval_id: str) -> bool:
        if not get_current_trust_context().can_approve:
            return False
        approval_id = str(approval_id)
        ticket = self._pending_actions.pop(approval_id, None)
        if ticket is None:
            return False
        request = ticket.request
        self._audit(
            request,
            "denied",
            action_id=ticket.action_id,
            permission=ticket.permission,
            approved=False,
            params=thaw_mapping(request.arguments),
            error="MCP action cancelled by user",
            metadata={"approval_id": approval_id},
        )
        return True

    def process_call(
        self,
        content: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> TaskExecutionResult:
        match = _MCP_CALL_RE.search(content or "")
        if not match:
            return TaskExecutionResult((), "")
        server, tool = match.group(1), match.group(2)
        arguments: dict[str, Any] = {}
        tail = content[match.end():]
        for raw in tail.splitlines():
            line = raw.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if not key or key.upper() in {"MCP_CALL", "SKILL_CALL"}:
                continue
            arguments[key] = self._coerce(value.strip())
        result = self.execute(
            server,
            tool,
            arguments,
            context=context,
        )
        return TaskExecutionResult((result,), str(result))

    @staticmethod
    def _coerce(value: str) -> Any:
        if not value:
            return ""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def _preflight(self, request, config, decision) -> str | None:
        if not config.execution_enabled:
            return f"MCP execution is disabled for server {request.server}"
        if request.tool not in config.allowed_tools:
            return f"MCP tool is not allowlisted: {request.server}.{request.tool}"
        descriptor = self.host.capabilities.get(request.action)
        if descriptor is None:
            return f"MCP tool is not discovered: {request.server}.{request.tool}"
        if not descriptor.available:
            return f"MCP tool is unavailable: {request.server}.{request.tool}"
        if decision.level == PermissionLevel.FORBIDDEN:
            return decision.reason
        return None

    def _invoke(self, request, config, decision, *, action_id, approved: bool):
        args = thaw_mapping(request.arguments)
        self._audit(
            request, "started", action_id=action_id,
            permission=decision.level.value, approved=approved, params=args,
        )
        try:
            result = self.host.mcp.call_tool(request.server, request.tool, args)
            encoded = json.dumps(result, ensure_ascii=False, default=str).encode("utf-8")
            if len(encoded) > config.result_limit_bytes:
                raise ValueError(
                    f"MCP result exceeds {config.result_limit_bytes} byte limit"
                )
            if bool(result.get("isError", False)):
                raise RuntimeError("MCP server reported a tool error")
            normalized = {
                "success": True,
                "server": request.server,
                "tool": request.tool,
                "output": dict(result),
            }
            self._audit(
                request, "completed", action_id=action_id,
                permission=decision.level.value, approved=approved, result=normalized,
            )
            return normalized
        except Exception as exc:
            error = str(exc)
            self._audit(
                request, "failed", action_id=action_id,
                permission=decision.level.value, approved=approved, params=args, error=error,
            )
            return self._error(request, error)

    def _audit(self, request, status: str, **kwargs):
        audit = getattr(self.host, "audit", None)
        if audit is None:
            return kwargs.get("action_id")
        metadata = dict(kwargs.pop("metadata", {}) or {})
        if request.context:
            metadata["execution_context"] = thaw_mapping(request.context)
        if metadata:
            kwargs["metadata"] = metadata
        return audit.record(
            actor_type="mcp",
            action=request.action,
            status=status,
            **kwargs,
        )

    @staticmethod
    def _error(request, error: str, *, permission_denied: bool = False):
        result = {
            "success": False,
            "error": str(error),
            "server": request.server,
            "tool": request.tool,
        }
        if permission_denied:
            result["permission_denied"] = True
        return result

    def _denied(self, request, error: str):
        self._audit(
            request, "denied", approved=False,
            params=thaw_mapping(request.arguments), error=error,
        )
        return self._error(request, error, permission_denied=True)
