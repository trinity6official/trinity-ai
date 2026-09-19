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
    host.response_processor = SimpleNamespace(
        check_skill_call_loop=MagicMock(return_value=(False, "")),
        fix_skill_call_format=MagicMock(side_effect=lambda content: content),
        record_skill_failure=MagicMock(),
        clean_response=MagicMock(side_effect=lambda content: content),
    )
    host.skill_evolution = MagicMock()
    host._invoke_with_failover = MagicMock(return_value=_Response("final answer"))
    host.conversation = SimpleNamespace(_save_to_history=MagicMock())
    host._conversation_history = []
    host.consciousness = MagicMock()
    host.memory = MagicMock()
    host.memory.get_current_focus.return_value = None
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
    host.conversation._save_to_history.assert_called_once_with("what is 1+2", "final answer")


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
    host.response_processor.record_skill_failure.assert_called_once()
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

    host.skill_evolution.propose_missing_tool.assert_called_once_with("fixture", "inspect_x", {}, llm)


def test_stuck_task_is_stopped_before_execution():
    host = _host([{"success": True}])
    host.response_processor.check_skill_call_loop.return_value = (True, "Stopped repeated call")
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

    host.skill_evolution.propose_new_skill.assert_called_once_with(
        "email", "inbox triage is unavailable", "check my inbox"
    )

def test_current_objective_focus_is_passed_as_skill_execution_context():
    host = _host([{"success": True, "value": 3}])
    host.memory.get_current_focus.return_value = {
        "id": "obj-1",
        "title": "Ship Trinity",
    }
    service = ConversationTaskService(host)

    service.handle(
        content="SKILL_CALL: calculator.calculate\nexpression: 1+2",
        question="calculate this",
        system_prompt="system",
        llm=object(),
    )

    host.skills.process_skill_call.assert_called_once_with(
        "SKILL_CALL: calculator.calculate\nexpression: 1+2",
        context={
            "objective_id": "obj-1",
            "objective_title": "Ship Trinity",
        },
    )


def test_current_objective_focus_is_passed_as_mcp_execution_context():
    host = _host([{"success": True}])
    host.mcp_execution = MagicMock()
    host.mcp_execution.process_call.return_value = SimpleNamespace(
        has_results=True,
        results=({"success": True},),
        rendered_text="rendered",
        failed=False,
        unknown_tool=None,
    )
    host.memory.get_current_focus.return_value = {
        "id": "obj-2",
        "title": "Review local files",
    }
    service = ConversationTaskService(host)

    service.handle(
        content="MCP_CALL: local-files.read_file\npath: /tmp/a",
        question="read it",
        system_prompt="system",
        llm=object(),
    )

    host.mcp_execution.process_call.assert_called_once_with(
        "MCP_CALL: local-files.read_file\npath: /tmp/a",
        context={
            "objective_id": "obj-2",
            "objective_title": "Review local files",
        },
    )
