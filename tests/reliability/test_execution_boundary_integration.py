from __future__ import annotations

import json

import pytest

from core.audit import ActionAuditTrail
from core.events import EventBus
from core.skill_manager import SkillManager
from core.trust_context import RequestSource, TrustContext, use_trust_context


pytestmark = [pytest.mark.contract, pytest.mark.integration]


class RecordingSkill:
    """Deterministic in-process capability used without mocking internal Trinity code."""

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, dict, bool]] = []

    def get_tools(self):
        return [
            {"name": "read_value", "needs_approval": False},
            {"name": "send_message", "needs_approval": False},
        ]

    def execute(self, tool_name, params, approved=False):
        self.calls.append((tool_name, dict(params), approved))
        if self.fail:
            raise RuntimeError("deterministic capability failure")
        return {"success": True, "tool": tool_name, "params": dict(params)}


def _audit_entries(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _manager(tmp_path, skill):
    bus = EventBus()
    observed = []
    bus.subscribe("*", observed.append)
    audit_path = tmp_path / "audit.jsonl"
    manager = SkillManager(audit_trail=ActionAuditTrail(audit_path, event_bus=bus))
    manager._skill_cache["fixture"] = skill
    return manager, audit_path, observed


def test_safe_capability_executes_once_through_permission_and_audit_boundary(tmp_path):
    skill = RecordingSkill()
    manager, audit_path, observed = _manager(tmp_path, skill)

    result = manager.execute("fixture", "read_value", {"key": "status"})

    assert result == {"success": True, "tool": "read_value", "params": {"key": "status"}}
    assert skill.calls == [("read_value", {"key": "status"}, False)]
    entries = _audit_entries(audit_path)
    assert [entry["status"] for entry in entries] == ["requested", "started", "completed"]
    assert len({entry["action_id"] for entry in entries}) == 1
    assert entries[0]["permission"] == "safe"
    assert any(event.type == "action.completed" for event in observed)


def test_confirmation_capability_cannot_execute_before_approval(tmp_path):
    skill = RecordingSkill()
    manager, audit_path, _ = _manager(tmp_path, skill)

    blocked = manager.execute("fixture", "send_message", {"to": "external"})

    assert blocked["success"] is False
    assert blocked["needs_approval"] is True
    assert blocked["permission"] == "confirm"
    assert skill.calls == []
    approval_id = blocked["approval_id"]
    assert manager.get_pending_actions()[approval_id]["tool"] == "send_message"

    completed = manager.approve_action(approval_id)

    assert completed["success"] is True
    assert skill.calls == [("send_message", {"to": "external"}, True)]
    assert manager.get_pending_actions() == {}
    statuses = [entry["status"] for entry in _audit_entries(audit_path)]
    assert statuses == [
        "requested",
        "approval_required",
        "requested",
        "approved",
        "started",
        "completed",
    ]


def test_unverified_request_escalates_safe_read_to_confirmation(tmp_path):
    skill = RecordingSkill()
    manager, _, _ = _manager(tmp_path, skill)
    unverified = TrustContext.unverified(source=RequestSource.LOCAL_VOICE)

    with use_trust_context(unverified):
        result = manager.execute("fixture", "read_value", {"key": "status"})

    assert result["success"] is False
    assert result["needs_approval"] is True
    assert result["permission"] == "confirm"
    assert skill.calls == []


@pytest.mark.failure_path
def test_capability_exception_is_contained_and_audited(tmp_path):
    skill = RecordingSkill(fail=True)
    manager, audit_path, _ = _manager(tmp_path, skill)

    result = manager.execute("fixture", "read_value", {})

    assert result["success"] is False
    assert "deterministic capability failure" in result["error"]
    assert skill.calls == [("read_value", {}, False)]
    entries = _audit_entries(audit_path)
    assert [entry["status"] for entry in entries] == ["requested", "started", "failed"]
    assert entries[-1]["error"] == "deterministic capability failure"


@pytest.mark.scenario
def test_llm_style_skill_call_uses_the_same_execution_boundary(tmp_path):
    """Characterize today's parser->policy->executor path before it is replaced."""
    skill = RecordingSkill()
    manager, audit_path, _ = _manager(tmp_path, skill)

    results, rendered = manager.process_skill_call(
        "Checking now.\nSKILL_CALL: fixture.read_value\nkey: health"
    )

    assert results == [{"success": True, "tool": "read_value", "params": {"key": "health"}}]
    assert "[fixture.read_value result]" in rendered
    assert skill.calls == [("read_value", {"key": "health"}, False)]
    assert [entry["status"] for entry in _audit_entries(audit_path)] == [
        "requested", "started", "completed"
    ]
