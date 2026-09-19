from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.agent_runtime import AgentContext, AgentRegistry
from core.audit import ActionAuditTrail
from core.capabilities import CapabilityRegistry
from core.execution import ExecutionRequest
from core.mcp import MCPServerConfig, MCPServerHealth, MCPTool
from core.mcp_execution import MCPExecutionService
from core.permissions import PermissionEngine
from core.skill_manager import SkillManager
from core.trust_context import RequestSource, TrustContext, use_trust_context


pytestmark = [pytest.mark.contract, pytest.mark.integration]


class ConfirmationSkill:
    name = "fixture"

    def __init__(self):
        self.calls = []

    def get_tools(self):
        return [{"name": "send_message", "needs_approval": False}]

    def execute(self, tool, params, approved=False):
        self.calls.append((tool, dict(params), approved))
        return {"success": True, "output": "sent"}


def _entries(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_skill_ticket_is_only_approval_proof_and_preserves_action_id(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    skill = ConfirmationSkill()
    manager = SkillManager(audit_trail=ActionAuditTrail(audit_path))
    manager._skill_cache["fixture"] = skill

    pending = manager.execute("fixture", "send_message", {"to": "client"})
    assert pending["needs_approval"] is True
    assert skill.calls == []

    completed = manager.approve_action(pending["approval_id"])
    assert completed["success"] is True
    assert skill.calls == [("send_message", {"to": "client"}, True)]

    entries = _entries(audit_path)
    assert [entry["status"] for entry in entries] == [
        "requested",
        "approval_required",
        "approved",
        "started",
        "completed",
    ]
    assert len({entry["action_id"] for entry in entries}) == 1


def test_unverified_caller_cannot_consume_skill_ticket():
    skill = ConfirmationSkill()
    manager = SkillManager()
    manager._skill_cache["fixture"] = skill
    pending = manager.execute("fixture", "send_message", {"to": "client"})

    unverified = TrustContext.unverified(source=RequestSource.LOCAL_VOICE)
    with use_trust_context(unverified):
        rejected = manager.approve_action(pending["approval_id"])

    assert rejected["success"] is False
    assert rejected["permission_denied"] is True
    assert pending["approval_id"] in manager.get_pending_actions()
    assert skill.calls == []


def test_agent_ticket_is_only_approval_proof_and_preserves_action_id(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    registry = AgentRegistry(audit_trail=ActionAuditTrail(audit_path))
    seen = []
    registry.register(
        "client",
        lambda ctx: seen.append(ctx.approved) or "sent",
        action_type="contacting_clients",
    )

    pending = registry.execute("client", AgentContext("contact client"))
    assert pending.requires_approval is True
    assert pending.approval_id
    assert seen == []

    completed = registry.approve_action(pending.approval_id)
    assert completed.success is True
    assert seen == [True]

    entries = _entries(audit_path)
    assert [entry["status"] for entry in entries] == [
        "requested",
        "approval_required",
        "approved",
        "started",
        "completed",
    ]
    assert len({entry["action_id"] for entry in entries}) == 1


class FakeMCP:
    def __init__(self):
        self.calls = []
        self._config = MCPServerConfig(
            name="remote",
            command="demo",
            trust="untrusted",
            execution_enabled=True,
            allowed_tools=("read_file",),
        )

    def config(self, name):
        if name != "remote":
            raise KeyError(name)
        return self._config

    def cached_tools(self):
        return (
            MCPTool(
                server="remote",
                name="read_file",
                description="read",
                input_schema={"type": "object"},
            ),
        )

    def health(self, name):
        return MCPServerHealth(
            name=name,
            enabled=True,
            running=True,
            initialized=True,
            pid=1,
            protocol_version="2025-06-18",
            tool_count=1,
            last_error=None,
            stderr_tail=(),
        )

    def call_tool(self, server, tool, arguments):
        self.calls.append((server, tool, dict(arguments)))
        return {"content": [{"type": "text", "text": "ok"}]}


def _mcp_service(tmp_path=None):
    mcp = FakeMCP()
    permissions = PermissionEngine()
    audit = ActionAuditTrail(
        (tmp_path / "audit.jsonl") if tmp_path is not None else None
    )
    host = SimpleNamespace(
        mcp=mcp,
        permissions=permissions,
        audit=audit,
    )
    host.capabilities = CapabilityRegistry(permissions, mcp=mcp)
    return MCPExecutionService(host), mcp


def test_mcp_ticket_preserves_original_action_id(tmp_path):
    service, mcp = _mcp_service(tmp_path)

    pending = service.execute("remote", "read_file", {"path": "/tmp/a"})
    completed = service.approve_action(pending["approval_id"])

    assert completed["success"] is True
    assert len(mcp.calls) == 1
    entries = _entries(tmp_path / "audit.jsonl")
    assert [entry["status"] for entry in entries] == [
        "requested",
        "approval_required",
        "approved",
        "started",
        "completed",
    ]
    assert len({entry["action_id"] for entry in entries}) == 1


def test_unverified_caller_cannot_consume_agent_or_mcp_ticket():
    registry = AgentRegistry()
    registry.register(
        "client",
        lambda ctx: "sent",
        action_type="contacting_clients",
    )
    agent_pending = registry.execute("client", AgentContext("contact client"))

    service, mcp = _mcp_service()
    mcp_pending = service.execute("remote", "read_file", {})

    unverified = TrustContext.unverified(source=RequestSource.LOCAL_VOICE)
    with use_trust_context(unverified):
        agent_result = registry.approve_action(agent_pending.approval_id)
        mcp_result = service.approve_action(mcp_pending["approval_id"])

    assert agent_result.success is False
    assert agent_pending.approval_id in registry.get_pending_actions()
    assert mcp_result["success"] is False
    assert mcp_result["permission_denied"] is True
    assert mcp_pending["approval_id"] in service.get_pending_actions()
    assert mcp.calls == []


def test_execution_request_has_no_approval_field():
    request = ExecutionRequest("fixture", "send_message", {"to": "client"})
    assert not hasattr(request, "approved")
