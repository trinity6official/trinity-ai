from unittest.mock import MagicMock

from core.commands import CommandHandler


def make_host():
    host = MagicMock()
    host.skills.get_pending_changes.return_value = {}
    host.response_processor = MagicMock()
    host.status_service = MagicMock()
    host.briefings = MagicMock()
    return host


def test_unknown_command_is_not_consumed():
    assert CommandHandler(make_host()).handle("/unknown") is False


def test_help_resets_failures_and_sends_help():
    host = make_host()
    assert CommandHandler(host).handle("/help", "english") is True
    host.response_processor.reset_skill_failures.assert_called_once()
    host.status_service.send_help.assert_called_once_with("english")


def test_briefing_command_runs_briefing():
    host = make_host()
    CommandHandler(host).handle("/briefing")
    host.briefings.deliver_morning.assert_called_once()


def test_pending_command_reports_empty_state():
    host = make_host()
    CommandHandler(host).handle("/pending")
    host.respond.assert_called_with("No pending changes.")


def test_status_delegates_to_host():
    host = make_host()
    CommandHandler(host).handle("/status")
    host.status_service.send_status.assert_called_once()


def test_pending_command_includes_skill_evolution_review():
    host = make_host()
    host.skill_evolution.get_pending_changes.return_value = {
        "p1": {
            "id": "p1",
            "path": "skills/email_skill.py",
            "reason": "Create email skill",
            "review": "--- /dev/null\n+++ skills/email_skill.py\n+class EmailSkill:",
        }
    }
    host.skills.get_pending_actions.return_value = {}

    CommandHandler(host).handle("/pending")
    message = host.respond.call_args.args[0]
    assert "Trinity skill improvement" in message
    assert "Exact diff under review" in message
    assert "+class EmailSkill:" in message

def test_objective_command_preserves_arguments_and_case():
    host = make_host()
    host.memory.create_objective.return_value = {
        "id": "abcdef123456",
        "title": "Build Trinity6 Demo",
    }

    CommandHandler(host).handle(
        "/objective add Build Trinity6 Demo",
        "english",
    )

    host.memory.create_objective.assert_called_once_with(
        "Build Trinity6 Demo"
    )
