"""
Tests for core/skill_manager.py — SkillManager

SkillManager is the routing layer between Trinity's LLM responses
and actual skill execution. The most failure-prone method is
process_skill_call(), which parses a custom text protocol from LLM
output and dispatches tool calls. Parsing bugs here silently swallow
tool calls or pass wrong types to skills.
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def sm():
    from core.skill_manager import SkillManager
    return SkillManager()


# ── init / get_skill ──────────────────────────────────────────────


class TestInit:
    def test_cache_empty_on_creation(self, sm):
        assert sm._skill_cache == {}

    def test_get_unknown_skill_returns_none(self, sm):
        result = sm.get_skill("nonexistent_skill")
        assert result is None

    def test_get_skill_caches_result(self, sm):
        mock_skill = MagicMock()
        sm._skill_cache["memory"] = mock_skill
        result = sm.get_skill("memory")
        assert result is mock_skill

    def test_get_skill_does_not_reload_cached(self, sm):
        mock_skill = MagicMock()
        sm._skill_cache["web"] = mock_skill
        sm.get_skill("web")
        sm.get_skill("web")
        # The cached object should be returned both times — no re-instantiation


# ── execute ───────────────────────────────────────────────────────


class TestExecute:
    def test_execute_unknown_skill_returns_error_dict(self, sm):
        result = sm.execute("ghost_skill", "ghost_tool")
        assert result["success"] is False
        assert "ghost_skill" in result["error"]

    def test_execute_unknown_skill_includes_available_skills(self, sm):
        result = sm.execute("ghost_skill", "ghost_tool")
        assert "available_skills" in result
        assert "memory" in result["available_skills"]

    def test_execute_delegates_to_skill(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {"success": True, "data": "ok"}
        sm._skill_cache["memory"] = mock_skill

        result = sm.execute("memory", "read_brain", {"section": "david"})
        mock_skill.execute.assert_called_once_with("read_brain", {"section": "david"})
        assert result["success"] is True

    def test_execute_defaults_params_to_empty_dict(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {}
        sm._skill_cache["memory"] = mock_skill

        sm.execute("memory", "read_brain")
        mock_skill.execute.assert_called_once_with("read_brain", {})

    def test_execute_catches_skill_exception(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.side_effect = RuntimeError("Skill exploded")
        sm._skill_cache["web"] = mock_skill

        result = sm.execute("web", "check_website", {"url": "https://example.com"})
        assert result["success"] is False
        assert "web.check_website" in result["error"]


# ── pending changes ───────────────────────────────────────────────


class TestPendingChanges:
    def test_get_pending_changes_no_github_skill(self, sm):
        assert sm.get_pending_changes() == {}

    def test_commit_change_no_github_skill(self, sm):
        success, msg = sm.commit_change("some_id")
        assert success is False
        assert "not available" in msg.lower()

    def test_cancel_change_no_github_skill(self, sm):
        result = sm.cancel_change("some_id")
        assert result is False

    def test_get_pending_changes_delegates_to_github_skill(self, sm):
        mock_github = MagicMock()
        mock_github.get_pending_changes.return_value = {"change_1": {}}
        sm._skill_cache["github"] = mock_github

        result = sm.get_pending_changes()
        assert result == {"change_1": {}}


# ── process_skill_call (parser) ───────────────────────────────────


class TestProcessSkillCall:
    def test_no_skill_call_marker_returns_none_and_text(self, sm):
        text = "This is a plain response with no skill calls."
        result_list, result_text = sm.process_skill_call(text)
        assert result_list is None
        assert "plain response" in result_text

    def test_skill_call_parsed_and_executed(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {"success": True}
        sm._skill_cache["memory"] = mock_skill

        text = (
            "Before call\n"
            "SKILL_CALL\n"
            "skill: memory\n"
            "tool: read_brain\n"
            "params:\n"
            "END_SKILL_CALL\n"
            "After call"
        )
        result_list, _ = sm.process_skill_call(text)
        assert result_list is not None
        mock_skill.execute.assert_called_once_with("read_brain", {})

    def test_string_param_passed_correctly(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {}
        sm._skill_cache["github"] = mock_skill

        text = (
            "SKILL_CALL\n"
            "skill: github\n"
            "tool: read_file\n"
            "params:\n"
            "repo: trinity-ai\n"
            "path: README.md\n"
            "END_SKILL_CALL\n"
        )
        sm.process_skill_call(text)
        call_params = mock_skill.execute.call_args[0][1]
        assert call_params["repo"] == "trinity-ai"
        assert call_params["path"] == "README.md"

    def test_integer_param_cast_to_int(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {}
        sm._skill_cache["github"] = mock_skill

        text = (
            "SKILL_CALL\n"
            "skill: github\n"
            "tool: get_commits\n"
            "params:\n"
            "count: 10\n"
            "END_SKILL_CALL\n"
        )
        sm.process_skill_call(text)
        call_params = mock_skill.execute.call_args[0][1]
        assert call_params["count"] == 10
        assert isinstance(call_params["count"], int)

    def test_float_param_cast_to_float(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {}
        sm._skill_cache["business"] = mock_skill

        text = (
            "SKILL_CALL\n"
            "skill: business\n"
            "tool: record_revenue\n"
            "params:\n"
            "amount: 9999.99\n"
            "END_SKILL_CALL\n"
        )
        sm.process_skill_call(text)
        call_params = mock_skill.execute.call_args[0][1]
        assert call_params["amount"] == 9999.99
        assert isinstance(call_params["amount"], float)

    def test_result_injected_into_output_text(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {"result": "brain data"}
        sm._skill_cache["memory"] = mock_skill

        text = (
            "SKILL_CALL\n"
            "skill: memory\n"
            "tool: read_brain\n"
            "params:\n"
            "END_SKILL_CALL\n"
        )
        result_list, result_text = sm.process_skill_call(text)
        assert "[memory.read_brain result]" in result_text

    def test_multiple_skill_calls_in_one_response(self, sm):
        mock_memory = MagicMock()
        mock_memory.execute.return_value = {}
        mock_web = MagicMock()
        mock_web.execute.return_value = {}
        sm._skill_cache["memory"] = mock_memory
        sm._skill_cache["web"] = mock_web

        text = (
            "SKILL_CALL\n"
            "skill: memory\n"
            "tool: read_brain\n"
            "params:\n"
            "END_SKILL_CALL\n"
            "SKILL_CALL\n"
            "skill: web\n"
            "tool: check_website\n"
            "params:\n"
            "url: https://trinity6.com\n"
            "END_SKILL_CALL\n"
        )
        sm.process_skill_call(text)
        assert mock_memory.execute.call_count == 1
        assert mock_web.execute.call_count == 1

    def test_text_outside_skill_call_preserved(self, sm):
        mock_skill = MagicMock()
        mock_skill.execute.return_value = {}
        sm._skill_cache["memory"] = mock_skill

        text = (
            "Here is some important context.\n"
            "SKILL_CALL\n"
            "skill: memory\n"
            "tool: read_brain\n"
            "params:\n"
            "END_SKILL_CALL\n"
            "And here is the conclusion."
        )
        _, result_text = sm.process_skill_call(text)
        assert "Here is some important context." in result_text
        assert "And here is the conclusion." in result_text
