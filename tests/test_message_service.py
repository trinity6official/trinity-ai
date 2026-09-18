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
    host.ask_trinity = MagicMock(return_value="answer")
    host.clean_response_for_david = lambda value: value
    host.respond = MagicMock()
    return host


def test_normal_message_uses_same_conversation_pipeline_and_responder():
    host = _host(); sent=[]
    result = MessageService(host).handle("hello", responder=sent.append)
    assert result == "answer"
    assert sent == ["Thinking...", "answer"]
    host.ask_trinity.assert_called_once_with("hello", "english")


def test_pending_change_approval_commits_once():
    host = _host(); sent=[]
    host.skills.get_pending_changes.return_value = {
        "c1": {"repo": "trinity-ai", "path": "README.md"}
    }
    host.skills.commit_change.return_value = (True, "committed")
    result = MessageService(host).handle("YES", responder=sent.append)
    assert result.startswith("Done!")
    host.skills.commit_change.assert_called_once_with("c1")
    host.ask_trinity.assert_not_called()


def test_pending_change_rejection_cancels_without_llm():
    host = _host(); sent=[]
    host.skills.get_pending_changes.return_value = {
        "c1": {"repo": "trinity-ai", "path": "README.md"}
    }
    result = MessageService(host).handle("CANCEL", responder=sent.append)
    assert "cancelled" in result.lower()
    host.skills.cancel_change.assert_called_once_with("c1")
    host.ask_trinity.assert_not_called()


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
    host.ask_trinity.assert_not_called()
