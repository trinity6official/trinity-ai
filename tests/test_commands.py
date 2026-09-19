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

def test_pending_command_shows_ids_and_requires_target_when_multiple():
    host = make_host()
    host.skills.get_pending_changes.return_value = {
        "change-1": {
            "repo": "trinity-ai",
            "path": "README.md",
            "reason": "update docs",
        }
    }
    host.skill_evolution.get_pending_changes.return_value = {}
    host.skills.get_pending_actions.return_value = {
        "action-1": {
            "skill": "computer",
            "tool": "open_app",
            "params": {"app_name": "Safari"},
        }
    }
    host.mcp_execution.get_pending_actions.return_value = {}

    CommandHandler(host).handle("/pending")

    message = host.respond.call_args.args[0]
    assert "ID: change-1" in message
    assert "ID: action-1" in message
    assert "Multiple approvals are pending" in message
    assert "APPROVE <id>" in message
    assert "REJECT <id>" in message

def test_skill_backed_command_carries_current_objective_context():
    host = make_host()
    host.memory.get_current_focus.return_value = {
        "id": "objective-123",
        "title": "Ship Trinity",
    }
    host.execute_skill_conscious.side_effect = (
        lambda skill, method, args, execute_fn: execute_fn()
    )
    host.skills.execute.return_value = {
        "success": True,
        "health_score": 100,
        "revenue": 0,
        "total_clients": 0,
        "total_prospects": 0,
        "days_building": 1,
        "next_milestone": "test",
        "alerts": [],
    }

    CommandHandler(host).handle("/business")

    host.skills.execute.assert_called_once_with(
        "business",
        "get_business_status",
        {},
        context={
            "objective_id": "objective-123",
            "objective_title": "Ship Trinity",
        },
    )


def test_progress_uses_governed_github_tool_instead_of_direct_skill_method():
    host = make_host()
    host.memory.get_current_focus.return_value = None
    host.execute_skill_conscious.side_effect = (
        lambda skill, method, args, execute_fn: execute_fn()
    )
    host.skills.execute.return_value = {
        "trinity-ai": {
            "total_files": 10,
            "recent_commits": [],
        }
    }

    CommandHandler(host).handle("/progress")

    host.skills.execute.assert_called_once_with(
        "github",
        "get_all_repos_context",
        {},
        context={},
    )
    host.skills.get_skill.assert_not_called()


def test_client_command_reuses_existing_pipeline_and_outreach_tools():
    host = make_host()
    host.memory.get_current_focus.return_value = None
    host.execute_skill_conscious.side_effect = (
        lambda skill, method, args, execute_fn: execute_fn()
    )

    def execute(skill, tool, params, context=None):
        assert skill == "business"
        assert context == {}
        if tool == "get_client_pipeline":
            return {
                "success": True,
                "total_in_pipeline": 2,
                "summary": {
                    "prospects": 1,
                    "in_discussion": 1,
                    "active": 0,
                },
            }
        if tool == "plan_outreach":
            assert params == {"target_count": 10}
            return {
                "success": True,
                "weekly_target": 10,
                "plan": [
                    {
                        "day": "Monday",
                        "actions": ["Send connection requests"],
                    }
                ],
                "templates": {
                    "connection_request": "Hello [Name]",
                },
            }
        raise AssertionError(f"Unexpected tool: {tool}")

    host.skills.execute.side_effect = execute

    CommandHandler(host).handle("/client")

    tools = [call.args[1] for call in host.skills.execute.call_args_list]
    assert tools == ["get_client_pipeline", "plan_outreach"]
    message = host.respond.call_args.args[0]
    assert "Client Strategy" in message
    assert "Weekly outreach target: 10" in message
