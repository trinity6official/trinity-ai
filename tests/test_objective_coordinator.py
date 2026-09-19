from types import SimpleNamespace
from unittest.mock import MagicMock

from core.audit import ActionAuditTrail
from core.events import EventBus
from core.memory import MemoryService
from core.objective_coordinator import ObjectiveEventCoordinator
from core.process_manager import ProcessManager, ProcessStatus


def build_host(tmp_path):
    events = EventBus()
    memory = MemoryService(
        brain_file=tmp_path / "memory" / "trinity_brain.json",
    )
    processes = ProcessManager(
        path=tmp_path / "runtime" / "processes.db",
        event_bus=events,
    )
    proactive_service = SimpleNamespace(check=MagicMock())
    return SimpleNamespace(
        events=events,
        memory=memory,
        processes=processes,
        proactive_service=proactive_service,
        audit=None,
    )


def test_unlinked_process_is_ignored_without_reasoning(tmp_path):
    host = build_host(tmp_path)
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()
    host.processes.register_handler(
        "work",
        lambda context, payload: {"ok": True},
    )

    process = host.processes.submit("work", {"value": 1})
    result = host.processes.run(process.id)

    assert result.status == ProcessStatus.SUCCEEDED
    host.proactive_service.check.assert_not_called()
    assert not [
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    ]


def test_explicit_success_progress_updates_without_llm_in_event_handler(tmp_path):
    host = build_host(tmp_path)
    objective = host.memory.create_objective("Prepare demo", make_focus=True)
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()
    host.processes.register_handler(
        "work",
        lambda context, payload: {"ok": True},
    )

    process = host.processes.submit(
        "work",
        {
            "objective_id": objective["id"],
            "objective_progress_on_success": 0.6,
        },
    )
    result = host.processes.run(process.id)

    assert result.status == ProcessStatus.SUCCEEDED
    assert host.memory.get_objective(objective["id"])["progress"] == 0.6
    host.proactive_service.check.assert_not_called()


def test_focused_failure_blocks_when_explicit_and_queues_review(tmp_path):
    host = build_host(tmp_path)
    objective = host.memory.create_objective("Prepare demo", make_focus=True)
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()

    def fail(context, payload):
        raise RuntimeError("installer failed")

    host.processes.register_handler("work", fail)
    process = host.processes.submit(
        "work",
        {
            "objective_id": objective["id"],
            "objective_blocking": True,
        },
    )

    result = host.processes.run(process.id)

    assert result.status == ProcessStatus.FAILED
    updated = host.memory.get_objective(objective["id"])
    assert updated["status"] == "blocked"
    assert "installer failed" in updated["blocked_reason"]

    # Reasoning has only been queued; the synchronous event path did not call it.
    host.proactive_service.check.assert_not_called()
    review = next(
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    )
    assert review.status == ProcessStatus.QUEUED

    review_result = host.processes.run(review.id)

    assert review_result.status == ProcessStatus.SUCCEEDED
    host.proactive_service.check.assert_called_once()
    trigger = host.proactive_service.check.call_args.kwargs["trigger_context"]
    assert "Prepare demo" in trigger
    assert "installer failed" in trigger


def test_nonfocused_failure_does_not_reason_unless_explicitly_requested(tmp_path):
    host = build_host(tmp_path)
    focus = host.memory.create_objective("Current focus", make_focus=True)
    background = host.memory.create_objective("Background objective")
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()

    def fail(context, payload):
        raise RuntimeError("background failed")

    host.processes.register_handler("work", fail)
    process = host.processes.submit(
        "work",
        {"objective_id": background["id"]},
    )
    result = host.processes.run(process.id)

    assert result.status == ProcessStatus.FAILED
    assert host.memory.get_current_focus()["id"] == focus["id"]
    host.proactive_service.check.assert_not_called()
    assert not [
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    ]


def test_explicit_review_on_success_is_deferred_through_process_manager(tmp_path):
    host = build_host(tmp_path)
    objective = host.memory.create_objective("Review after import")
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()
    host.processes.register_handler(
        "import",
        lambda context, payload: {"rows": 10},
    )

    process = host.processes.submit(
        "import",
        {
            "objective_id": objective["id"],
            "objective_review": True,
        },
    )
    host.processes.run(process.id)

    host.proactive_service.check.assert_not_called()
    review = next(
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    )
    host.processes.run(review.id)

    host.proactive_service.check.assert_called_once()


def test_terminal_objective_events_do_not_reopen_or_review(tmp_path):
    host = build_host(tmp_path)
    objective = host.memory.create_objective("Already done")
    host.memory.set_objective_status(
        objective["id"],
        "completed",
        reason="done",
    )
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()
    host.processes.register_handler(
        "work",
        lambda context, payload: {"ok": True},
    )

    process = host.processes.submit(
        "work",
        {
            "objective_id": objective["id"],
            "objective_review": True,
            "objective_progress_on_success": 0.5,
        },
    )
    host.processes.run(process.id)

    stored = host.memory.get_objective(objective["id"])
    assert stored["status"] == "completed"
    assert stored["progress"] == 1.0
    host.proactive_service.check.assert_not_called()


def test_stop_unsubscribes_terminal_event_handlers(tmp_path):
    host = build_host(tmp_path)
    objective = host.memory.create_objective(
        "Stopped coordinator",
        make_focus=True,
    )
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()
    coordinator.stop()

    host.processes.register_handler(
        "work",
        lambda context, payload: {"ok": True},
    )
    process = host.processes.submit(
        "work",
        {
            "objective_id": objective["id"],
            "objective_review": True,
        },
    )
    host.processes.run(process.id)

    assert not [
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    ]

def test_focused_action_failure_queues_deferred_objective_review(tmp_path):
    host = build_host(tmp_path)
    host.audit = ActionAuditTrail(path=None, event_bus=host.events)
    objective = host.memory.create_objective(
        "Ship Trinity",
        make_focus=True,
    )
    coordinator = ObjectiveEventCoordinator(host)
    coordinator.start()

    host.audit.record(
        actor_type="skill",
        action="web.check_website",
        status="failed",
        error="offline",
        metadata={
            "execution_context": {
                "objective_id": objective["id"],
                "objective_title": objective["title"],
            }
        },
    )

    host.proactive_service.check.assert_not_called()
    review = next(
        item
        for item in host.processes.list()
        if item.kind == ObjectiveEventCoordinator.REVIEW_PROCESS_KIND
    )
    assert review.status == ProcessStatus.QUEUED

    host.processes.run(review.id)

    host.proactive_service.check.assert_called_once()
    trigger = host.proactive_service.check.call_args.kwargs["trigger_context"]
    assert "action=web.check_website" in trigger
    assert "offline" in trigger
