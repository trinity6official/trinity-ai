from unittest.mock import MagicMock

from core.commands import CommandHandler


def make_host():
    host = MagicMock()
    host.skills.get_pending_changes.return_value = {}
    return host


def test_unknown_command_is_not_consumed():
    assert CommandHandler(make_host()).handle("/unknown") is False


def test_help_resets_failures_and_sends_help():
    host = make_host()
    assert CommandHandler(host).handle("/help", "english") is True
    host.reset_skill_failures.assert_called_once()
    host.send_help.assert_called_once_with("english")


def test_briefing_command_runs_briefing():
    host = make_host()
    CommandHandler(host).handle("/briefing")
    host.deliver_morning_briefing.assert_called_once()


def test_pending_command_reports_empty_state():
    host = make_host()
    CommandHandler(host).handle("/pending")
    host.respond.assert_called_with("No pending changes.")


def test_status_delegates_to_host():
    host = make_host()
    CommandHandler(host).handle("/status")
    host.send_status.assert_called_once()
