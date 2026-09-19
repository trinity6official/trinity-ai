from types import SimpleNamespace
from unittest.mock import MagicMock

from core.events import EventBus
from core.memory import MemoryService
from core.objective_commands import ObjectiveCommandService


def host_for(tmp_path):
    return SimpleNamespace(
        memory=MemoryService(
            brain_file=tmp_path / "memory" / "trinity_brain.json",
        ),
        events=EventBus(),
        respond=MagicMock(),
    )


def last_message(host):
    return host.respond.call_args.args[0]


def test_add_preserves_title_case_and_does_not_assume_focus(tmp_path):
    host = host_for(tmp_path)
    service = ObjectiveCommandService(host)

    assert service.handle("/objective add Build Trinity6 Launch Demo") is True

    items = host.memory.list_objectives()
    assert len(items) == 1
    assert items[0]["title"] == "Build Trinity6 Launch Demo"
    assert host.memory.get_current_focus() is None
    assert "Set focus with:" in last_message(host)


def test_focus_accepts_unique_short_id(tmp_path):
    host = host_for(tmp_path)
    objective = host.memory.create_objective("Ship local voice")
    service = ObjectiveCommandService(host)

    service.handle(f"/objective focus {objective['id'][:8]}")

    assert host.memory.get_current_focus()["id"] == objective["id"]
    assert "Current focus: Ship local voice" in last_message(host)


def test_pause_current_focus_preserves_objective_and_clears_focus(tmp_path):
    host = host_for(tmp_path)
    objective = host.memory.create_objective(
        "Finish integration",
        make_focus=True,
    )
    service = ObjectiveCommandService(host)

    service.handle(f"/objective pause {objective['id'][:8]}")

    stored = host.memory.get_objective(objective["id"])
    assert stored["status"] == "paused"
    assert host.memory.get_current_focus() is None


def test_progress_command_converts_percent_to_bounded_fraction(tmp_path):
    host = host_for(tmp_path)
    objective = host.memory.create_objective("Prepare release")
    service = ObjectiveCommandService(host)

    service.handle(
        f"/objective progress {objective['id'][:8]} 65"
    )

    assert host.memory.get_objective(objective["id"])["progress"] == 0.65
    assert "65%" in last_message(host)


def test_complete_marks_progress_100_and_removes_focus(tmp_path):
    host = host_for(tmp_path)
    objective = host.memory.create_objective(
        "Complete migration",
        make_focus=True,
    )
    service = ObjectiveCommandService(host)

    service.handle(f"/objective complete {objective['id'][:8]}")

    stored = host.memory.get_objective(objective["id"])
    assert stored["status"] == "completed"
    assert stored["progress"] == 1.0
    assert host.memory.get_current_focus() is None


def test_objectives_lists_focus_and_hides_terminal_by_default(tmp_path):
    host = host_for(tmp_path)
    active = host.memory.create_objective("Active objective", make_focus=True)
    done = host.memory.create_objective("Completed objective")
    host.memory.set_objective_status(done["id"], "completed")
    service = ObjectiveCommandService(host)

    service.handle("/objectives")

    message = last_message(host)
    assert active["id"][:8] in message
    assert "FOCUS" in message
    assert "Completed objective" not in message

    service.handle("/objectives all")
    assert "Completed objective" in last_message(host)


def test_invalid_progress_is_reported_without_mutation(tmp_path):
    host = host_for(tmp_path)
    objective = host.memory.create_objective("Safe progress")
    service = ObjectiveCommandService(host)

    service.handle(
        f"/objective progress {objective['id'][:8]} 120"
    )

    assert host.memory.get_objective(objective["id"])["progress"] == 0.0
    assert "0 to 100" in last_message(host)


def test_clear_focus_does_not_change_objective_status(tmp_path):
    host = host_for(tmp_path)
    objective = host.memory.create_objective("Keep active", make_focus=True)
    service = ObjectiveCommandService(host)

    service.handle("/objective clear-focus")

    assert host.memory.get_current_focus() is None
    assert host.memory.get_objective(objective["id"])["status"] == "active"
