import json

from core.agent_runtime import AgentContext, AgentRegistry
from core.audit import ActionAuditTrail, sanitize
from core.events import EventBus
from core.permissions import PermissionEngine
from core.skill_manager import SkillManager


def _entries(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_sanitize_redacts_nested_secrets():
    value = {"token": "abc", "nested": {"api_key": "def", "safe": "ok"}}
    cleaned = sanitize(value)
    assert cleaned["token"] == "<redacted>"
    assert cleaned["nested"]["api_key"] == "<redacted>"
    assert cleaned["nested"]["safe"] == "ok"


def test_audit_persists_and_emits_events(tmp_path):
    bus = EventBus(); seen = []
    bus.subscribe("action.completed", seen.append)
    path = tmp_path / "audit.jsonl"
    audit = ActionAuditTrail(path, event_bus=bus)
    action_id = audit.record(
        actor_type="skill", action="calculator.calculate", status="completed",
        params={"expression": "1+1", "token": "secret"}, result={"value": 2},
    )
    entries = _entries(path)
    assert entries[0]["action_id"] == action_id
    assert entries[0]["params"]["token"] == "<redacted>"
    assert seen and seen[0].payload["action"] == "calculator.calculate"


def test_skill_execution_has_requested_started_completed(tmp_path, monkeypatch):
    class EchoSkill:
        name = "echo"
        def execute(self, tool, params):
            return {"success": True, "value": params.get("value")}

    audit = ActionAuditTrail(tmp_path / "audit.jsonl")
    permissions = PermissionEngine()
    manager = SkillManager(permission_engine=permissions, audit_trail=audit)
    monkeypatch.setattr(manager, "get_skill", lambda name: EchoSkill())

    result = manager.execute("echo", "read_value", {"value": 7})
    assert result["value"] == 7
    assert [e["status"] for e in _entries(tmp_path / "audit.jsonl")] == [
        "requested", "started", "completed"
    ]


def test_agent_approval_and_completion_are_audited(tmp_path):
    audit = ActionAuditTrail(tmp_path / "audit.jsonl")
    registry = AgentRegistry(audit_trail=audit)
    registry.register("scanner", lambda ctx: "ok", action_type="network_scanning")

    blocked = registry.execute("scanner", AgentContext("scan"))
    assert blocked.requires_approval is True
    approved = registry.execute("scanner", AgentContext("scan", approved=True))
    assert approved.success is True

    statuses = [entry["status"] for entry in _entries(tmp_path / "audit.jsonl")]
    assert statuses == [
        "requested", "approval_required",
        "requested", "approved", "started", "completed",
    ]


def test_approved_commit_is_audited(tmp_path):
    audit = ActionAuditTrail(tmp_path / "audit.jsonl")
    manager = SkillManager(audit_trail=audit)
    manager._skill_cache["github"] = type(
        "GitHub", (), {"commit_change": lambda self, cid: (True, "done")}
    )()
    assert manager.commit_change("change-1") == (True, "done")
    statuses = [entry["status"] for entry in _entries(tmp_path / "audit.jsonl")]
    assert statuses == ["requested", "approved", "started", "completed"]
