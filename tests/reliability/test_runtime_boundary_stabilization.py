from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.audit import ActionAuditTrail
from core.commands import CommandHandler
from core.conversation import ConversationService
from core.memory import MemoryService
from core.message_service import MessageService
from core.orchestrator import MessageOrchestrator
from core.permissions import PermissionEngine
from core.skill_evolution import SkillEvolutionService
from core.skill_manager import SkillManager
from core.trust_context import RequestSource, TrustContext, use_trust_context

pytestmark = [pytest.mark.contract, pytest.mark.integration]


def _message_host():
    skills = MagicMock()
    skills.get_pending_changes.return_value = {}
    skills.get_pending_actions.return_value = {}
    language = MagicMock()
    language.detect_and_respond.return_value = {"language": "english"}
    language.get_response_prefix.return_value = {"thinking": "Thinking..."}
    consciousness = MagicMock()
    memory = MagicMock()
    host = SimpleNamespace(
        skills=skills,
        language=language,
        consciousness=consciousness,
        memory=memory,
        orchestrator=MessageOrchestrator(),
        commands=MagicMock(),
        events=None,
    )
    host.commands.handle.return_value = False
    host.conversation = SimpleNamespace(ask_trinity=MagicMock(return_value="answer"))
    host.respond = MagicMock()
    return host


@pytest.mark.scenario
def test_unverified_voice_cannot_approve_pending_action():
    host = _message_host()
    host.skills.get_pending_actions.return_value = {
        "action-1": {
            "skill": "computer",
            "tool": "open_app",
            "params": {"app_name": "Safari"},
        }
    }
    host.skills.approve_action = MagicMock()
    replies = []
    with use_trust_context(TrustContext.unverified(source=RequestSource.LOCAL_VOICE)):
        result = MessageService(host).handle(
            "APPROVE action-1", responder=replies.append, source="voice"
        )
    assert "Owner verification is required" in result
    host.skills.approve_action.assert_not_called()
    host.memory.update_david_last_seen.assert_not_called()
    host.consciousness.add_working.assert_not_called()


@pytest.mark.scenario
def test_unverified_voice_cannot_run_private_commands():
    host = _message_host()
    host.commands.handle = MagicMock(return_value=True)
    with use_trust_context(TrustContext.unverified(source=RequestSource.LOCAL_VOICE)):
        result = MessageService(host).handle(
            "/brain", responder=lambda _message: None, source="voice"
        )
    assert "Owner verification is required" in result
    host.commands.handle.assert_not_called()


@pytest.mark.scenario
def test_unverified_conversation_does_not_load_private_context_or_tools():
    llm = object()
    memory = MagicMock()
    consciousness = MagicMock()
    skills = MagicMock()
    host = SimpleNamespace(
        events=None,
        memory=memory,
        consciousness=consciousness,
        skills=skills,
        response_processor=SimpleNamespace(clean_response=lambda value: value),
        get_llm_for_task=lambda _question: llm,
        _invoke_with_failover=lambda messages, preferred_llm=None: SimpleNamespace(
            content="general answer"
        ),
    )
    service = ConversationService(host)
    with use_trust_context(TrustContext.unverified(source=RequestSource.LOCAL_VOICE)):
        result = service.ask_trinity("What is DNS?", "english")
    assert result == "general answer"
    memory.get_full_context.assert_not_called()
    consciousness.recall.assert_not_called()
    consciousness.set_focus.assert_not_called()
    skills.get_trinity_prompt.assert_not_called()


@pytest.mark.failure_path
def test_unverified_memory_read_retains_permission_escalation():
    class MemoryRead:
        name = "memory"
        def get_tools(self):
            return [{"name": "read_brain", "needs_approval": False}]
        def execute(self, tool, params):
            return {"success": True, "private": "must-not-run"}

    manager = SkillManager(permission_engine=PermissionEngine())
    manager._skill_cache["memory"] = MemoryRead()
    with use_trust_context(TrustContext.unverified(source=RequestSource.LOCAL_VOICE)):
        result = manager.execute("memory", "read_brain", {})
    assert result["needs_approval"] is True
    assert result["skill"] == "memory"
    assert result["tool"] == "read_brain"


@pytest.mark.failure_path
def test_error_only_skill_result_is_audited_as_failed(tmp_path):
    class BrokenSkill:
        name = "broken"
        def execute(self, tool, params):
            return {"error": "boom"}

    path = tmp_path / "audit.jsonl"
    manager = SkillManager(
        permission_engine=PermissionEngine(),
        audit_trail=ActionAuditTrail(path),
    )
    manager._skill_cache["broken"] = BrokenSkill()
    manager.execute("broken", "read_value", {})
    statuses = [
        json.loads(line)["status"]
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    assert statuses == ["requested", "started", "failed"]


@pytest.mark.failure_path
def test_command_stops_when_skill_requires_approval():
    host = MagicMock()
    host.memory.get_current_focus.return_value = None
    host.execute_skill_conscious.side_effect = (
        lambda skill, method, args, execute_fn: execute_fn()
    )
    host.skills.execute.return_value = {
        "success": False,
        "needs_approval": True,
        "approval_id": "approve-1",
        "skill": "business",
        "tool": "get_business_status",
    }
    assert CommandHandler(host).handle("/business") is True
    assert "APPROVE approve-1" in host.respond.call_args.args[0]


@pytest.mark.failure_path
def test_failed_skill_evolution_restores_previous_source(tmp_path):
    path = tmp_path / "demo_skill.py"
    original = "class DemoSkill:\n    name='demo'\n"
    path.write_text(original, encoding="utf-8")
    generated = (
        "class DemoSkill:\n"
        "    name='demo'\n"
        "    def read_x(self): return {'success': True}\n"
    )
    skills = MagicMock()
    skills.get_skill.return_value = None
    host = SimpleNamespace(
        skills=skills,
        audit=None,
        respond=MagicMock(),
        consciousness=MagicMock(),
    )
    host._invoke_with_failover = lambda *a, **k: SimpleNamespace(content=generated)
    service = SkillEvolutionService(host, tmp_path)
    service.propose_missing_tool("demo", "read_x", {}, object())
    proposal_id = next(iter(service.get_pending_changes()))
    success, _ = service.approve(proposal_id)
    assert success is False
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.failure_path
def test_objective_creation_rolls_back_when_persistence_fails(tmp_path, monkeypatch):
    memory = MemoryService(memory_root=tmp_path / "memory")
    def fail_save(*_args, **_kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(memory.store, "save_state", fail_save)
    with pytest.raises(RuntimeError, match="Memory persistence failed"):
        memory.create_objective("Must not become ghost state")
    assert memory.list_objectives() == []


def test_aggregation_services_do_not_directly_invoke_skill_objects():
    for relative in ("core/briefing.py", "core/status_service.py"):
        source = Path(relative).read_text(encoding="utf-8")
        assert ".get_skill(" not in source
