from types import SimpleNamespace
from unittest.mock import MagicMock

from core.conversation_tasks import ConversationTaskService


class _Response:
    def __init__(self, content):
        self.content = content


def _host(results):
    host = SimpleNamespace()
    host.respond = MagicMock()
    host.skills = MagicMock()
    host.skills.process_skill_call.return_value = (results, "rendered")
    host.check_skill_call_loop = MagicMock(return_value=(False, ""))
    host.fix_skill_call_format = MagicMock(side_effect=lambda content: content)
    host.record_skill_failure = MagicMock()
    host._auto_implement_missing_tool = MagicMock()
    host._auto_build_new_skill = MagicMock()
    host._invoke_with_failover = MagicMock(return_value=_Response("final answer"))
    host.clean_response_for_david = MagicMock(side_effect=lambda content: content)
    host._save_to_history = MagicMock()
    host._conversation_history = []
    host.consciousness = MagicMock()
    return host


def test_successful_task_emits_status_and_runs_one_followup():
    host = _host([{"success": True, "value": 3}])
    service = ConversationTaskService(host)

    response = service.handle(
        content="SKILL_CALL: calculator.calculate\nexpression: 1+2",
        question="what is 1+2",
        system_prompt="system",
        llm=object(),
    )

    assert response == "final answer"
    host.respond.assert_called_once_with("Working on it (calculate)...")
    host.skills.process_skill_call.assert_called_once()
    host._invoke_with_failover.assert_called_once()
    host._save_to_history.assert_called_once_with("what is 1+2", "final answer")


def test_failed_task_records_failure_and_does_not_retry_capability():
    host = _host([{"success": False, "error": "offline"}])
    service = ConversationTaskService(host)

    response = service.handle(
        content="SKILL_CALL: web.check_website\nurl: https://example.com",
        question="check it",
        system_prompt="system",
        llm=object(),
    )

    assert response == "final answer"
    host.record_skill_failure.assert_called_once()
    assert host.skills.process_skill_call.call_count == 1
    followup_messages = host._invoke_with_failover.call_args.args[0]
    assert "Do NOT retry the same call" in followup_messages[-1].content


def test_unknown_tool_routes_to_approval_gated_proposal_boundary():
    host = _host([
        {
            "success": False,
            "error": "Unknown tool: inspect_x",
            "unknown_tool": True,
            "skill": "fixture",
            "tool": "inspect_x",
        }
    ])
    service = ConversationTaskService(host)
    llm = object()

    service.handle(
        content="SKILL_CALL: fixture.inspect_x",
        question="inspect x",
        system_prompt="system",
        llm=llm,
    )

    host._auto_implement_missing_tool.assert_called_once_with("fixture", "inspect_x", {}, llm)


def test_stuck_task_is_stopped_before_execution():
    host = _host([{"success": True}])
    host.check_skill_call_loop.return_value = (True, "Stopped repeated call")
    service = ConversationTaskService(host)

    response = service.handle(
        content="Looking now\nSKILL_CALL: web.check_website",
        question="check it",
        system_prompt="system",
        llm=object(),
    )

    assert response == "Looking now\n\nStopped repeated call"
    host.skills.process_skill_call.assert_not_called()

def test_skill_need_directive_routes_to_governed_builder(monkeypatch):
    host = _host([])
    service = ConversationTaskService(host)
    monkeypatch.setattr("core.conversation_tasks.os.path.exists", lambda _path: False)

    service.process_skill_need_directives(
        "TRINITY_SKILL_NEED: email | inbox triage is unavailable",
        "check my inbox",
    )

    host._auto_build_new_skill.assert_called_once_with(
        "email", "inbox triage is unavailable", "check my inbox"
    )
