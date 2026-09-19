from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.audit import ActionAuditTrail
from core.events import EventBus
from core.memory import MemoryService
from core.objective_coordinator import ObjectiveEventCoordinator
from core.process_manager import ProcessManager, ProcessStatus
from core.skill_manager import SkillManager


pytestmark = [pytest.mark.integration, pytest.mark.scenario]


class ConfirmationSkill:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def get_tools(self):
        return [{"name": "send_message", "needs_approval": False}]

    def execute(self, tool_name, params, approved=False):
        self.calls.append((tool_name, dict(params), approved))
        if self.fail:
            raise RuntimeError("approved action failed")
        return {
            "success": True,
            "output": "sent",
        }


def build_runtime(tmp_path, skill):
    events = EventBus()
    memory = MemoryService(
        brain_file=tmp_path / "memory" / "trinity_brain.json",
    )
    audit = ActionAuditTrail(path=None, event_bus=events)
    processes = ProcessManager(
        path=tmp_path / "runtime" / "processes.db",
        event_bus=events,
        audit_trail=audit,
    )
    proactive_service = SimpleNamespace(check=MagicMock())
    host = SimpleNamespace(
        events=events,
        memory=memory,
        audit=audit,
        processes=processes,
        proactive_service=proactive_service,
    )
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()

    manager = SkillManager(
        memory=memory,
        audit_trail=audit,
    )
    manager._skill_cache["fixture"] = skill
    return host, coordinator, manager


def objective_context(objective):
    return {
        "objective_id": objective["id"],
        "objective_title": objective["title"],
    }


def review_processes(host):
    return [
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    ]


def test_approved_success_preserves_objective_context_and_stays_quiet(tmp_path):
    skill = ConfirmationSkill()
    host, coordinator, manager = build_runtime(tmp_path, skill)
    objective = host.memory.create_objective(
        "Reach a client",
        make_focus=True,
    )

    pending = manager.execute(
        "fixture",
        "send_message",
        {"to": "client"},
        context=objective_context(objective),
    )

    assert pending["needs_approval"] is True
    assert pending["skill"] == "fixture"
    assert pending["tool"] == "send_message"
    assert skill.calls == []

    snapshot = manager.get_pending_actions()[pending["approval_id"]]
    assert snapshot["context"] == objective_context(objective)

    completed = manager.approve_action(pending["approval_id"])

    assert completed["success"] is True
    assert skill.calls == [
        ("send_message", {"to": "client"}, True)
    ]
    assert review_processes(host) == []
    host.proactive_service.check.assert_not_called()
    coordinator.stop()


def test_approved_failure_keeps_original_objective_and_queues_review(tmp_path):
    skill = ConfirmationSkill(fail=True)
    host, coordinator, manager = build_runtime(tmp_path, skill)
    objective = host.memory.create_objective(
        "Reach a client",
        make_focus=True,
    )

    pending = manager.execute(
        "fixture",
        "send_message",
        {"to": "client"},
        context=objective_context(objective),
    )

    failed = manager.approve_action(pending["approval_id"])

    assert failed["success"] is False
    assert "approved action failed" in failed["error"]
    assert skill.calls == [
        ("send_message", {"to": "client"}, True)
    ]

    reviews = review_processes(host)
    assert len(reviews) == 1
    assert reviews[0].status == ProcessStatus.QUEUED
    assert (
        reviews[0].payload["linked_objective_id"]
        == objective["id"]
    )

    # The audit/event path stays cheap. Reasoning happens only when
    # ProcessManager executes the deferred objective.review process.
    host.proactive_service.check.assert_not_called()
    review_result = host.processes.run(reviews[0].id)

    assert review_result.status == ProcessStatus.SUCCEEDED
    host.proactive_service.check.assert_called_once()
    trigger = host.proactive_service.check.call_args.kwargs["trigger_context"]
    assert "fixture.send_message" in trigger
    assert "approved action failed" in trigger
    coordinator.stop()
