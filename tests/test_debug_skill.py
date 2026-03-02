"""
Real tests for debug_skill.py

All tests call the actual DebugSkill code.
test_skill_method() is tested with a real SkillManager — proves it actually executes.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.debug_skill import DebugSkill
from core.skill_manager import SkillManager


@pytest.fixture
def debug():
    """DebugSkill without skill_manager (for isolated tests)."""
    return DebugSkill()


@pytest.fixture
def debug_with_sm():
    """DebugSkill with a real SkillManager (for integration tests)."""
    sm = SkillManager()
    return DebugSkill(skill_manager=sm), sm


# ── log_error() ───────────────────────────────────────────────────────────────


class TestLogError:
    def test_log_stores_entry(self, debug):
        r = debug.log_error("web", "check_website", "Connection refused")
        assert r["success"] is True
        assert r["total_errors"] == 1

    def test_log_stores_all_fields(self, debug):
        debug.log_error("github", "read_file", "404 Not Found", {"repo": "test"})
        entry = debug._error_log[-1]
        assert entry["skill"] == "github"
        assert entry["tool"] == "read_file"
        assert entry["error"] == "404 Not Found"
        assert entry["params"] == {"repo": "test"}

    def test_log_caps_at_200(self, debug):
        for i in range(210):
            debug.log_error("web", "check_website", f"Error {i}")
        assert len(debug._error_log) == 200
        # Most recent entries kept
        assert "Error 209" in debug._error_log[-1]["error"]

    def test_log_default_params_none(self, debug):
        debug.log_error("memory", "read_brain", "IOError")
        entry = debug._error_log[-1]
        assert entry["params"] == {}

    def test_execute_routes_log_error(self, debug):
        r = debug.execute("log_error", {
            "skill_name": "search",
            "tool_name": "search_web",
            "error_message": "Timeout",
        })
        assert r["success"] is True


# ── analyze_error() ───────────────────────────────────────────────────────────


class TestAnalyzeError:
    def test_classifies_importerror(self, debug):
        r = debug.analyze_error("ModuleNotFoundError: No module named 'bs4'")
        assert r["success"] is True
        assert r["error_type"] == "ImportError"
        assert "pip install" in r["fix_suggestion"]

    def test_classifies_keyerror(self, debug):
        r = debug.analyze_error("KeyError: 'content'")
        assert r["success"] is True
        assert r["error_type"] == "KeyError"
        assert ".get(" in r["fix_suggestion"]

    def test_classifies_typeerror(self, debug):
        r = debug.analyze_error("TypeError: unexpected keyword argument 'path'")
        assert r["success"] is True
        assert r["error_type"] == "TypeError"

    def test_classifies_attributeerror(self, debug):
        r = debug.analyze_error("AttributeError: 'NoneType' has no attribute 'execute'")
        assert r["success"] is True
        assert r["error_type"] == "AttributeError"

    def test_classifies_network_error(self, debug):
        r = debug.analyze_error("ConnectionError: connection refused to port 443")
        assert r["success"] is True
        assert r["error_type"] == "NetworkError"

    def test_classifies_auth_error(self, debug):
        r = debug.analyze_error("403 Forbidden: bad credentials")
        assert r["success"] is True
        assert r["error_type"] == "AuthError"

    def test_classifies_zero_division(self, debug):
        r = debug.analyze_error("ZeroDivisionError: division by zero")
        assert r["success"] is True
        assert r["error_type"] == "ZeroDivisionError"

    def test_classifies_json_error(self, debug):
        r = debug.analyze_error("JSONDecodeError: Expecting value: line 1 column 1")
        assert r["success"] is True
        assert r["error_type"] == "JSONError"

    def test_classifies_file_not_found(self, debug):
        r = debug.analyze_error("FileNotFoundError: No such file or directory")
        assert r["success"] is True
        assert r["error_type"] == "FileNotFoundError"

    def test_unknown_error_returns_unknown(self, debug):
        r = debug.analyze_error("Something very strange happened with the flux capacitor")
        assert r["success"] is True
        assert r["error_type"] == "UnknownError"

    def test_returns_fix_suggestion_always(self, debug):
        r = debug.analyze_error("random weird error xyz")
        assert "fix_suggestion" in r
        assert len(r["fix_suggestion"]) > 10


# ── test_skill_method() — REAL EXECUTION ─────────────────────────────────────


class TestSkillMethodExecution:
    def test_no_skill_manager_returns_clear_error(self, debug):
        r = debug.test_skill_method("memory", "read_brain", {})
        assert r["success"] is False
        assert "skill_manager" in r["error"].lower()

    def test_executes_calculator_add(self, debug_with_sm):
        d, sm = debug_with_sm
        r = d.test_skill_method("calculator", "calculate", {"expression": "2 + 2"})
        assert r["success"] is True
        assert r["test_passed"] is True
        assert r["result"]["result"] == 4
        assert r["duration_ms"] >= 0

    def test_executes_calculator_mrr(self, debug_with_sm):
        d, sm = debug_with_sm
        r = d.test_skill_method(
            "calculator", "calculate_mrr",
            {"clients": 3, "price_per_client": 5000}
        )
        assert r["success"] is True
        assert r["test_passed"] is True
        assert r["result"]["mrr_inr"] == 15000

    def test_unknown_skill_passes_through_sm_error(self, debug_with_sm):
        d, sm = debug_with_sm
        r = d.test_skill_method("nonexistent_skill", "do_something", {})
        # Should succeed (test ran), but test_passed=False (skill not found)
        assert r["success"] is True
        assert r["test_passed"] is False

    def test_bad_params_detected(self, debug_with_sm):
        d, sm = debug_with_sm
        # Pass a string where a number is expected
        r = d.test_skill_method(
            "calculator", "calculate",
            {"expression": "open('/etc/passwd').read()"}
        )
        assert r["success"] is True
        assert r["test_passed"] is False  # calculator blocked it

    def test_duration_is_populated(self, debug_with_sm):
        d, sm = debug_with_sm
        r = d.test_skill_method("calculator", "calculate", {"expression": "1 + 1"})
        assert isinstance(r.get("duration_ms"), int)
        assert r["duration_ms"] >= 0

    def test_auto_logs_error_on_exception(self, debug_with_sm):
        d, sm = debug_with_sm
        initial_count = len(d._error_log)
        # Force an exception by injecting a broken mock
        import unittest.mock as mock
        with mock.patch.object(sm, 'execute', side_effect=RuntimeError("Boom")):
            r = d.test_skill_method("any", "tool", {})
        assert r["success"] is False
        assert len(d._error_log) > initial_count


# ── get_error_history() ───────────────────────────────────────────────────────


class TestErrorHistory:
    def test_empty_history(self, debug):
        r = debug.get_error_history()
        assert r["success"] is True
        assert r["total_errors"] == 0
        assert r["errors"] == []

    def test_history_after_logging(self, debug):
        debug.log_error("web", "check_ssl", "SSL expired")
        debug.log_error("github", "read_file", "404")
        r = debug.get_error_history(limit=10)
        assert r["total_errors"] == 2
        assert len(r["errors"]) == 2

    def test_limit_respected(self, debug):
        for i in range(20):
            debug.log_error("web", "check_website", f"Error {i}")
        r = debug.get_error_history(limit=5)
        assert len(r["errors"]) == 5

    def test_most_recent_returned(self, debug):
        for i in range(10):
            debug.log_error("web", "check_website", f"Error {i}")
        r = debug.get_error_history(limit=3)
        errors = r["errors"]
        assert "Error 9" in errors[-1]["error"]


# ── get_error_patterns() ─────────────────────────────────────────────────────


class TestErrorPatterns:
    def test_no_errors_returns_empty(self, debug):
        r = debug.get_error_patterns()
        assert r["success"] is True
        assert r["patterns"] == []

    def test_detects_recurring_failure(self, debug):
        for _ in range(3):
            debug.log_error("web", "check_ssl", "Timeout")
        r = debug.get_error_patterns()
        assert r["success"] is True
        recurring = r["recurring_failures"]
        assert any("web.check_ssl" in p["skill_tool"] for p in recurring)

    def test_most_failing_identified(self, debug):
        for _ in range(5):
            debug.log_error("github", "read_file", "404")
        for _ in range(2):
            debug.log_error("web", "check_website", "Timeout")
        r = debug.get_error_patterns()
        assert r["most_failing"] == "github.read_file"

    def test_single_occurrence_not_in_recurring(self, debug):
        debug.log_error("search", "search_web", "One-off error")
        r = debug.get_error_patterns()
        recurring = r.get("recurring_failures", [])
        assert not any("search.search_web" in p["skill_tool"] for p in recurring)


# ── clear_errors() ───────────────────────────────────────────────────────────


class TestClearErrors:
    def test_clear_resets_log(self, debug):
        debug.log_error("web", "check_website", "Error")
        debug.log_error("github", "read_file", "Error")
        r = debug.clear_errors()
        assert r["success"] is True
        assert r["cleared"] == 2
        assert len(debug._error_log) == 0

    def test_clear_empty_log_returns_zero(self, debug):
        r = debug.clear_errors()
        assert r["cleared"] == 0
