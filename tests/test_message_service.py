from types import SimpleNamespace
from unittest.mock import MagicMock

from core.message_service import MessageService
from core.orchestrator import MessageOrchestrator


def _host():
    skills = MagicMock()
    skills.get_pending_changes.return_value = {}
    language = MagicMock()
    language.detect_and_respond.return_value = {"language": "english"}
    language.get_response_prefix.return_value = {"thinking": "Thinking..."}
    consciousness = MagicMock()
    memory = MagicMock()
    host = SimpleNamespace(
        skills=skills, language=language, consciousness=consciousness, memory=memory,
        orchestrator=MessageOrchestrator(), commands=MagicMock(), events=None,
    )
    host.commands.handle.return_value = False
    host.conversation = SimpleNamespace(ask_trinity=MagicMock(return_value="answer"))
    host.respond = MagicMock()
    return host


def test_normal_message_uses_same_conversation_pipeline_and_responder():
    host = _host(); sent=[]
    result = MessageService(host).handle("hello", responder=sent.append)
    assert result == "answer"
    assert sent == ["Thinking...", "answer"]
    host.conversation.ask_trinity.assert_called_once_with("hello", "english")


def test_pending_change_approval_commits_once():
    host = _host(); sent=[]
    host.skills.get_pending_changes.return_value = {
        "c1": {"repo": "trinity-ai", "path": "README.md"}
    }
    host.skills.commit_change.return_value = (True, "committed")
    result = MessageService(host).handle("YES", responder=sent.append)
    assert result.startswith("Done!")
    host.skills.commit_change.assert_called_once_with("c1")
    host.conversation.ask_trinity.assert_not_called()


def test_pending_change_rejection_cancels_without_llm():
    host = _host(); sent=[]
    host.skills.get_pending_changes.return_value = {
        "c1": {"repo": "trinity-ai", "path": "README.md"}
    }
    result = MessageService(host).handle("CANCEL", responder=sent.append)
    assert "cancelled" in result.lower()
    host.skills.cancel_change.assert_called_once_with("c1")
    host.conversation.ask_trinity.assert_not_called()


def test_generic_pending_action_yes_resumes_tool():
    host = _host()
    host.skills.get_pending_actions = MagicMock(return_value={
        "abc": {"skill": "computer", "tool": "open_app", "params": {"app_name": "Safari"}}
    })
    host.skills.approve_action = MagicMock(return_value={"success": True, "output": "Opened Safari"})
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    replies = []
    result = MessageService(host).handle("YES", responder=replies.append, source="local")
    assert "Opened Safari" in result
    host.skills.approve_action.assert_called_once_with("abc")


def test_generic_pending_action_rejection_clears_without_execution():
    host = _host()
    host.skills.get_pending_actions = MagicMock(return_value={
        "abc": {"skill": "computer", "tool": "open_app", "params": {"app_name": "Safari"}}
    })
    host.skills.cancel_action = MagicMock(return_value=True)
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    replies = []
    result = MessageService(host).handle("NO", responder=replies.append, source="local")
    assert "cancelled" in result.lower()
    host.skills.cancel_action.assert_called_once_with("abc")
    host.skills.approve_action.assert_not_called()
    host.conversation.ask_trinity.assert_not_called()

def test_command_arguments_are_preserved_for_command_handler():
    host = _host()
    host.commands.handle.return_value = True

    MessageService(host).handle(
        "/objective add Build Trinity6 Demo",
        responder=lambda message: None,
    )

    host.commands.handle.assert_called_once_with(
        "/objective add Build Trinity6 Demo",
        "english",
    )
    host.conversation.ask_trinity.assert_not_called()

def test_plain_yes_refuses_to_guess_between_multiple_pending_approvals():
    host = _host()
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    host.skills.get_pending_actions = MagicMock(return_value={
        "skill-1": {
            "skill": "computer",
            "tool": "open_app",
            "params": {"app_name": "Safari"},
        }
    })
    host.skills.approve_action = MagicMock()
    host.mcp_execution = SimpleNamespace(
        get_pending_actions=lambda: {
            "mcp-1": {
                "server": "local-files",
                "tool": "update_file",
                "arguments": {"path": "/tmp/a"},
            }
        },
        approve_action=MagicMock(),
        cancel_action=MagicMock(),
    )

    replies = []
    result = MessageService(host).handle(
        "YES",
        responder=replies.append,
        source="local",
    )

    assert "Multiple approvals are pending" in result
    assert "skill-1" in result
    assert "mcp-1" in result
    assert "APPROVE <id>" in result
    host.skills.approve_action.assert_not_called()
    host.mcp_execution.approve_action.assert_not_called()
    host.conversation.ask_trinity.assert_not_called()


def test_targeted_approval_selects_only_requested_pending_action():
    host = _host()
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    host.skills.get_pending_actions = MagicMock(return_value={
        "skill-1": {
            "skill": "computer",
            "tool": "open_app",
            "params": {"app_name": "Safari"},
        }
    })
    host.skills.approve_action = MagicMock(
        return_value={"success": True, "output": "Opened Safari"}
    )
    mcp_approve = MagicMock()
    host.mcp_execution = SimpleNamespace(
        get_pending_actions=lambda: {
            "mcp-1": {
                "server": "local-files",
                "tool": "update_file",
                "arguments": {"path": "/tmp/a"},
            }
        },
        approve_action=mcp_approve,
        cancel_action=MagicMock(),
    )

    replies = []
    result = MessageService(host).handle(
        "APPROVE skill-1",
        responder=replies.append,
        source="local",
    )

    assert "Opened Safari" in result
    host.skills.approve_action.assert_called_once_with("skill-1")
    mcp_approve.assert_not_called()


def test_targeted_rejection_selects_only_requested_mcp_action():
    host = _host()
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    host.skills.get_pending_actions = MagicMock(return_value={
        "skill-1": {
            "skill": "computer",
            "tool": "open_app",
            "params": {"app_name": "Safari"},
        }
    })
    host.skills.cancel_action = MagicMock()
    mcp_cancel = MagicMock(return_value=True)
    host.mcp_execution = SimpleNamespace(
        get_pending_actions=lambda: {
            "mcp-1": {
                "server": "local-files",
                "tool": "update_file",
                "arguments": {"path": "/tmp/a"},
            }
        },
        approve_action=MagicMock(),
        cancel_action=mcp_cancel,
    )

    replies = []
    result = MessageService(host).handle(
        "REJECT mcp-1",
        responder=replies.append,
        source="local",
    )

    assert "MCP action cancelled" in result
    mcp_cancel.assert_called_once_with("mcp-1")
    host.skills.cancel_action.assert_not_called()


def test_unknown_targeted_approval_does_not_execute_any_pending_action():
    host = _host()
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    host.skills.get_pending_actions = MagicMock(return_value={
        "skill-1": {
            "skill": "computer",
            "tool": "open_app",
            "params": {"app_name": "Safari"},
        }
    })
    host.skills.approve_action = MagicMock()

    replies = []
    result = MessageService(host).handle(
        "APPROVE missing-id",
        responder=replies.append,
        source="local",
    )

    assert "No pending approval matches ID missing-id" in result
    host.skills.approve_action.assert_not_called()
    host.conversation.ask_trinity.assert_not_called()


def test_targeted_agent_approval_routes_only_to_agent_registry():
    host = _host()
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    host.skills.get_pending_actions = MagicMock(return_value={})
    agent_approve = MagicMock(
        return_value=SimpleNamespace(success=True, output="sent", error=None)
    )
    host.agents = SimpleNamespace(
        get_pending_actions=lambda: {
            "agent-1": {
                "agent": "client",
                "objective": "contact client",
                "data": {},
            }
        },
        approve_action=agent_approve,
        cancel_action=MagicMock(),
    )
    host.mcp_execution = SimpleNamespace(
        get_pending_actions=lambda: {},
        approve_action=MagicMock(),
        cancel_action=MagicMock(),
    )

    replies = []
    result = MessageService(host).handle(
        "APPROVE agent-1",
        responder=replies.append,
        source="local",
    )

    assert "sent" in result
    agent_approve.assert_called_once_with("agent-1")
    host.skills.approve_action.assert_not_called()


def test_targeted_agent_rejection_routes_only_to_agent_registry():
    host = _host()
    host.skill_evolution = SimpleNamespace(get_pending_changes=lambda: {})
    host.skills.get_pending_actions = MagicMock(return_value={})
    agent_cancel = MagicMock(return_value=True)
    host.agents = SimpleNamespace(
        get_pending_actions=lambda: {
            "agent-1": {
                "agent": "client",
                "objective": "contact client",
                "data": {},
            }
        },
        approve_action=MagicMock(),
        cancel_action=agent_cancel,
    )
    host.mcp_execution = SimpleNamespace(
        get_pending_actions=lambda: {},
        approve_action=MagicMock(),
        cancel_action=MagicMock(),
    )

    replies = []
    result = MessageService(host).handle(
        "REJECT agent-1",
        responder=replies.append,
        source="local",
    )

    assert "Agent action cancelled" in result
    agent_cancel.assert_called_once_with("agent-1")
    host.skills.cancel_action.assert_not_called()
