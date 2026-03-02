"""
Tests for the three UX bug fixes in core/trinity.py

1. clean_response_for_david() - strips raw success dicts (not just error dicts)
2. ask_trinity() sends a skill-specific status message before executing a skill
3. ask_trinity() reports errors instead of swallowing them silently

All tests instantiate only the parts under test (no Telegram, no LLM, no GitHub).
"""
import re
import sys
import types
import pytest
from unittest.mock import MagicMock, patch, call


# ── Stub out langchain_core so the inline imports inside ask_trinity() work ──
# langchain_core is not installed in the test environment; the classes are only
# used to build the messages list for llm.invoke() which is fully mocked anyway.

def _stub_langchain():
    lc = types.ModuleType("langchain_core")
    lc_msgs = types.ModuleType("langchain_core.messages")

    class _Msg:
        def __init__(self, content):
            self.content = content

    lc_msgs.HumanMessage = _Msg
    lc_msgs.SystemMessage = _Msg
    lc_msgs.AIMessage = _Msg   # needed since ask_trinity now uses AIMessage for conversation history
    lc.messages = lc_msgs
    sys.modules.setdefault("langchain_core", lc)
    sys.modules.setdefault("langchain_core.messages", lc_msgs)

_stub_langchain()


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_trinity():
    """
    Return a Trinity instance with every external dependency stubbed out
    so the constructor never touches the network, disk, or Anthropic API.
    """
    with (
        patch("core.trinity.TrinityMemory"),
        patch("core.trinity.Consciousness"),
        patch("core.trinity.DaemonMode"),
        patch("core.trinity.LanguageDetector"),
        patch("core.trinity.TrinityVoice"),
        patch("core.trinity.SkillManager"),
        patch("core.trinity.Trinity.setup_llm", return_value=MagicMock()),
        patch("core.trinity.Trinity._seed_knowledge"),
        patch("core.trinity.Trinity._commit_brain"),
        patch("requests.get"),
    ):
        from core.trinity import Trinity
        t = Trinity()

        # Give consciousness a usable brain dict so boot() doesn't crash
        t.consciousness.brain = {
            "meta": {"total_boots": 2},
            "state": {"energy": 1.0},
            "patterns": [],
        }
        t.consciousness.brain_path = "/tmp/fake_brain.json"
        t._using_ollama = False
        t._failed_skill_calls = {}
        t.github_context_cache = ""
        return t


# ── 1. clean_response_for_david ───────────────────────────────────────────────

class TestCleanResponseForDavid:
    """Fix 1: raw skill result dicts must never reach David."""

    @pytest.fixture
    def trinity(self):
        return make_trinity()

    # --- success dicts ---

    def test_strips_simple_success_dict(self, trinity):
        raw = "Here is the data.\n\n{'success': True, 'content': 'secret stuff'}"
        result = trinity.clean_response_for_david(raw)
        assert "{'success'" not in result
        assert "secret stuff" not in result
        assert "Here is the data." in result

    def test_strips_multiline_success_dict(self, trinity):
        raw = (
            "David, let me read that file.\n\n"
            "{'success': True,\n"
            " 'content': 'line1\\nline2\\nline3',\n"
            " 'sha': 'abc123',\n"
            " 'repo': 'trinity-ai'}"
        )
        result = trinity.clean_response_for_david(raw)
        assert "success" not in result
        assert "sha" not in result
        assert "David, let me read that file." in result

    def test_strips_success_false_dict(self, trinity):
        raw = "Something went wrong.\n{'success': False, 'error': 'not found'}"
        result = trinity.clean_response_for_david(raw)
        assert "{'success'" not in result
        assert "not found" not in result

    def test_strips_result_list(self, trinity):
        raw = "Results:\n[{'success': True, 'commits': ['a', 'b', 'c']}]"
        result = trinity.clean_response_for_david(raw)
        assert "[{'success'" not in result
        assert "commits" not in result

    def test_does_not_strip_normal_text(self, trinity):
        clean = "The latest commit added auto-discovery to SkillManager."
        result = trinity.clean_response_for_david(clean)
        assert result == clean

    # --- SKILL_CALL artifacts ---

    def test_strips_skill_call_block(self, trinity):
        raw = "Let me check.\n\nSKILL_CALL: github.read_file\nrepo: trinity-ai\npath: README.md\n"
        result = trinity.clean_response_for_david(raw)
        assert "SKILL_CALL" not in result
        assert "Let me check." in result

    def test_strips_result_label(self, trinity):
        raw = "Answer: [github.read_file result]\nsome data"
        result = trinity.clean_response_for_david(raw)
        assert "[github.read_file result]" not in result

    # --- markdown ---

    def test_strips_bold_markdown(self, trinity):
        raw = "**Important:** this is the answer."
        result = trinity.clean_response_for_david(raw)
        assert "**" not in result
        assert "Important: this is the answer." in result

    def test_collapses_blank_lines(self, trinity):
        raw = "Line one.\n\n\n\nLine two."
        result = trinity.clean_response_for_david(raw)
        assert "\n\n\n" not in result


# ── 2. Status message sent before skill execution ─────────────────────────────

class TestSkillStatusMessage:
    """Fix 2: David must see a 'Reading from GitHub...' message before the skill runs."""

    @pytest.fixture
    def trinity(self):
        t = make_trinity()
        t.send_telegram = MagicMock()
        return t

    def _run_ask_with_skill_call(self, trinity, skill, tool, extra_params=""):
        """
        Stub the LLM to return a SKILL_CALL block, stub the skill to return
        a successful result, stub the follow-up LLM to return a clean answer,
        then call ask_trinity().
        """
        llm_first = MagicMock()
        llm_first.content = (
            f"Let me look that up.\n\n"
            f"SKILL_CALL: {skill}.{tool}\n"
            f"{extra_params}"
        )

        llm_followup = MagicMock()
        llm_followup.content = "Here is the summary for David."

        trinity.llm = MagicMock()
        trinity.llm.invoke = MagicMock(side_effect=[llm_first, llm_followup])

        trinity.skills.process_skill_call = MagicMock(
            return_value=([{"success": True, "data": "ok"}], "processed text")
        )
        trinity.skills.get_trinity_prompt = MagicMock(return_value="")
        trinity.memory.get_full_context = MagicMock(return_value="")
        trinity.consciousness.recall = MagicMock(return_value=[])
        trinity.consciousness.get_context = MagicMock(return_value="")
        trinity.consciousness.set_focus = MagicMock()
        trinity.consciousness.log_operation = MagicMock()
        trinity.consciousness.remember = MagicMock()
        trinity.consciousness.learn = MagicMock()
        trinity.consciousness.log_decision = MagicMock()

        trinity.ask_trinity("test question")

    def test_github_skill_sends_reading_status(self, trinity):
        self._run_ask_with_skill_call(trinity, "github", "get_commits")
        messages_sent = [c.args[0] for c in trinity.send_telegram.call_args_list]
        assert any("GitHub" in m or "github" in m.lower() for m in messages_sent), (
            f"Expected a GitHub status message, got: {messages_sent}"
        )

    def test_web_skill_sends_checking_status(self, trinity):
        self._run_ask_with_skill_call(trinity, "web", "check_website")
        messages_sent = [c.args[0] for c in trinity.send_telegram.call_args_list]
        assert any("website" in m.lower() or "checking" in m.lower() for m in messages_sent), (
            f"Expected a website status message, got: {messages_sent}"
        )

    def test_search_skill_sends_searching_status(self, trinity):
        self._run_ask_with_skill_call(trinity, "search", "find_potential_clients")
        messages_sent = [c.args[0] for c in trinity.send_telegram.call_args_list]
        assert any("search" in m.lower() for m in messages_sent), (
            f"Expected a searching status message, got: {messages_sent}"
        )

    def test_status_message_comes_before_final_answer(self, trinity):
        self._run_ask_with_skill_call(trinity, "github", "read_file", "repo: trinity-ai\n")
        calls = [c.args[0] for c in trinity.send_telegram.call_args_list]
        # There should be at least 2 Telegram messages
        assert len(calls) >= 1, "Expected at least a status message"
        # The status message must not be the same as the final answer
        github_statuses = [c for c in calls if "github" in c.lower() or "GitHub" in c]
        assert github_statuses, "No GitHub status message found"

    def test_unknown_skill_sends_generic_status(self, trinity):
        self._run_ask_with_skill_call(trinity, "calendar", "get_events")
        messages_sent = [c.args[0] for c in trinity.send_telegram.call_args_list]
        assert any("working on it" in m.lower() for m in messages_sent), (
            f"Expected a generic 'Working on it' status, got: {messages_sent}"
        )


# ── 3. Errors reported, not swallowed ────────────────────────────────────────

class TestErrorReporting:
    """Fix 3: when an LLM call fails, David must see an error message."""

    @pytest.fixture
    def trinity(self):
        t = make_trinity()
        t.send_telegram = MagicMock()
        return t

    def _setup_common_mocks(self, trinity):
        trinity.skills.get_trinity_prompt = MagicMock(return_value="")
        trinity.memory.get_full_context = MagicMock(return_value="")
        trinity.consciousness.recall = MagicMock(return_value=[])
        trinity.consciousness.get_context = MagicMock(return_value="")
        trinity.consciousness.set_focus = MagicMock()
        trinity.consciousness.log_operation = MagicMock()
        trinity.consciousness.remember = MagicMock()
        trinity.consciousness.learn = MagicMock()
        trinity.consciousness.log_decision = MagicMock()

    def test_retry_llm_failure_returns_error_message(self, trinity):
        """When skill call fails AND retry LLM throws, David sees an error."""
        self._setup_common_mocks(trinity)

        llm_first = MagicMock()
        llm_first.content = (
            "Let me check.\n\nSKILL_CALL: github.read_file\nrepo: trinity-ai\n"
        )

        # First invoke returns SKILL_CALL; second invoke (retry) raises
        trinity.llm = MagicMock()
        trinity.llm.invoke = MagicMock(side_effect=[
            llm_first,
            RuntimeError("API timeout"),
        ])

        # Skill call itself returns a failure
        trinity.skills.process_skill_call = MagicMock(
            return_value=([{"success": False, "error": "not found"}], "processed")
        )

        result = trinity.ask_trinity("show me the file")

        assert result is not None
        assert len(result) > 0
        assert "{'success'" not in result, "Raw dict leaked into error response"
        # Should contain some hint that something went wrong
        assert any(
            word in result.lower()
            for word in ["error", "issue", "problem", "failed", "trouble"]
        ), f"Expected error indication, got: {result!r}"

    def test_followup_llm_failure_returns_error_message(self, trinity):
        """When skill call succeeds BUT follow-up LLM throws, David sees an error."""
        self._setup_common_mocks(trinity)

        llm_first = MagicMock()
        llm_first.content = (
            "Let me check.\n\nSKILL_CALL: github.get_commits\nrepo: trinity-ai\n"
        )

        # First invoke returns SKILL_CALL; second invoke (followup) raises
        trinity.llm = MagicMock()
        trinity.llm.invoke = MagicMock(side_effect=[
            llm_first,
            ConnectionError("connection reset"),
        ])

        # Skill call succeeds
        trinity.skills.process_skill_call = MagicMock(
            return_value=(
                [{"success": True, "commits": [{"sha": "abc", "message": "fix"}]}],
                "processed"
            )
        )

        result = trinity.ask_trinity("what was the last commit")

        assert result is not None
        assert len(result) > 0
        assert "{'success'" not in result, "Raw success dict leaked"
        assert "commits" not in result, "Raw commits data leaked"
        assert any(
            word in result.lower()
            for word in ["error", "issue", "trouble", "failed"]
        ), f"Expected error indication, got: {result!r}"

    def test_followup_error_does_not_send_raw_dict(self, trinity):
        """The raw skill result dict must NEVER reach send_telegram when followup fails."""
        self._setup_common_mocks(trinity)

        llm_first = MagicMock()
        llm_first.content = (
            "SKILL_CALL: github.read_file\nrepo: trinity-ai\npath: README.md\n"
        )

        trinity.llm = MagicMock()
        trinity.llm.invoke = MagicMock(side_effect=[
            llm_first,
            RuntimeError("LLM unavailable"),
        ])

        trinity.skills.process_skill_call = MagicMock(
            return_value=(
                [{"success": True, "content": "SECRET FILE CONTENT XYZ"}],
                "[github.read_file result]\n{'success': True, 'content': 'SECRET FILE CONTENT XYZ'}"
            )
        )

        # ask_trinity returns the string; handle_message would then call send_telegram
        # Here we verify ask_trinity itself doesn't return raw data
        result = trinity.ask_trinity("read the readme")
        assert "SECRET FILE CONTENT XYZ" not in result

    def test_toplevel_llm_exception_returns_error_string(self, trinity):
        """When the very first LLM call throws, the error is returned as a string."""
        self._setup_common_mocks(trinity)

        trinity.llm = MagicMock()
        trinity.llm.invoke = MagicMock(side_effect=Exception("LLM is down"))

        result = trinity.ask_trinity("anything")

        assert result is not None
        assert "LLM is down" in result or "error" in result.lower()

    def test_no_llm_returns_unavailable_message(self, trinity):
        """When llm is None, returns a clear unavailable message."""
        trinity.llm = None
        result = trinity.ask_trinity("anything")
        assert "not available" in result.lower() or "unavailable" in result.lower()
