from types import MappingProxyType

import pytest
from unittest.mock import MagicMock

from core.execution import ExecutionRequest, TaskExecutionResult
from core.skill_manager import SkillManager


def test_execution_request_normalizes_and_copies_params():
    params = {"key": "value"}
    request = ExecutionRequest(" Memory ", "read_brain", params)
    params["key"] = "changed"

    assert request.skill == "memory"
    assert request.tool == "read_brain"
    assert request.action == "memory.read_brain"
    assert request.params == {"key": "value"}
    with pytest.raises(TypeError):
        request.params["key"] = "mutated"


def test_execution_request_approved_copy_preserves_payload():
    request = ExecutionRequest("fixture", "send_message", {"to": "external"})
    approved = request.approved_copy()

    assert approved is not request
    assert approved.approved is True
    assert approved.skill == request.skill
    assert approved.tool == request.tool
    assert approved.params == request.params


def test_skill_manager_execute_request_is_authoritative_boundary():
    manager = SkillManager()
    skill = MagicMock()
    skill.execute.return_value = {"success": True, "value": 7}
    manager._skill_cache["fixture"] = skill

    result = manager.execute_request(
        ExecutionRequest("fixture", "read_value", MappingProxyType({"key": "status"}))
    )

    assert result == {"success": True, "value": 7}
    skill.execute.assert_called_once_with("read_value", {"key": "status"})


def test_legacy_execute_wrapper_builds_same_contract():
    manager = SkillManager()
    manager.execute_request = MagicMock(return_value={"success": True})

    result = manager.execute("fixture", "read_value", {"key": "status"}, approved=True)

    assert result == {"success": True}
    request = manager.execute_request.call_args.args[0]
    assert isinstance(request, ExecutionRequest)
    assert request.action == "fixture.read_value"
    assert request.params == {"key": "status"}
    assert request.approved is True


def test_task_execution_result_classifies_failure_and_unknown_tool():
    result = TaskExecutionResult(
        ({"success": False, "error": "Unknown tool: lookup", "skill": "fixture", "tool": "lookup"},),
        "rendered",
    )

    assert result.has_results is True
    assert result.failed is True
    assert result.unknown_tool["tool"] == "lookup"


def test_execution_request_recursively_freezes_and_snapshots_nested_params():
    original = {"files": [{"path": "a.txt", "content": "safe"}], "tags": ["one"]}
    request = ExecutionRequest("fixture", "write", original)

    original["files"][0]["content"] = "mutated externally"
    original["tags"].append("two")

    assert request.params["files"][0]["content"] == "safe"
    assert request.params["tags"] == ("one",)
    with pytest.raises(TypeError):
        request.params["files"][0]["content"] = "mutated internally"


def test_pending_action_returns_mutable_copy_without_mutating_request():
    request = ExecutionRequest("fixture", "write", {"files": [{"path": "a.txt"}]})
    pending = request.as_pending_action("abc", "confirm")
    pending["params"]["files"][0]["path"] = "changed.txt"
    assert request.params["files"][0]["path"] == "a.txt"
