from types import SimpleNamespace
from unittest.mock import MagicMock

from core.change_requests import ChangeRequestService


def _host(read_result):
    skills = MagicMock()
    skills.get_skill.return_value = object()
    skills.execute.side_effect = [read_result, {"success": True, "message": "staged"}]
    consciousness = MagicMock()
    host = SimpleNamespace(skills=skills, consciousness=consciousness)
    host.execute_skill_conscious = lambda skill, method, args, execute_fn: execute_fn()
    return host


def _block(content="new data"):
    return f"""TRINITY_CHANGE_REQUEST
repo: trinity-ai
file: README.md
reason: improve docs
content:
{content}
END_TRINITY_CHANGE"""


def test_existing_large_replacement_stages_update_through_skill_manager():
    host = _host({"success": True, "content": "x" * 10})
    result = ChangeRequestService(host).process(_block("y" * 8))
    assert result == "staged"
    assert host.skills.execute.call_args_list[-1].args[0:2] == ("github", "update_file")


def test_small_append_stages_add_to_file():
    host = _host({"success": True, "content": "x" * 100})
    ChangeRequestService(host).process(_block("short"))
    assert host.skills.execute.call_args_list[-1].args[0:2] == ("github", "add_to_file")


def test_missing_file_stages_create():
    host = _host({"success": False, "error": "missing"})
    ChangeRequestService(host).process(_block("new"))
    assert host.skills.execute.call_args_list[-1].args[0:2] == ("github", "create_file")


def test_invalid_block_fails_without_touching_github():
    host = _host({"success": True, "content": "x"})
    result = ChangeRequestService(host).process("TRINITY_CHANGE_REQUEST\nrepo: x")
    assert "Could not process" in result
    host.skills.execute.assert_not_called()
