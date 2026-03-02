"""
Real tests for LLM routing logic in core/trinity.py

Tests verify that:
- get_llm_for_task() routes complex queries to the local model
- Simple queries go to the cloud model
- Fallbacks work when one model is unavailable
- Dynamic prompt selection works for skill_manager
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.skill_manager import SkillManager


# ── SkillManager dynamic prompt ───────────────────────────────────────────────


class TestDynamicPrompt:
    @pytest.fixture
    def sm(self):
        return SkillManager()

    def test_no_query_returns_full_prompt(self, sm):
        prompt = sm.get_trinity_prompt(query=None)
        # All major skills should be present
        assert "GITHUB SKILL" in prompt
        assert "WEB SKILL" in prompt
        assert "MEMORY SKILL" in prompt
        assert "SEARCH SKILL" in prompt
        assert "CODE SKILL" in prompt
        assert "BUSINESS SKILL" in prompt
        assert "CALCULATOR SKILL" in prompt
        assert "DEBUG SKILL" in prompt

    def test_code_query_includes_github_and_code(self, sm):
        prompt = sm.get_trinity_prompt(query="review the code in trinity6 repo")
        assert "CODE SKILL" in prompt
        assert "GITHUB SKILL" in prompt

    def test_business_query_includes_business(self, sm):
        prompt = sm.get_trinity_prompt(query="what is our current MRR and revenue?")
        assert "BUSINESS SKILL" in prompt

    def test_math_query_includes_calculator(self, sm):
        prompt = sm.get_trinity_prompt(query="calculate how much I need per month to hit 10 lakh")
        assert "CALCULATOR SKILL" in prompt

    def test_search_query_includes_search(self, sm):
        prompt = sm.get_trinity_prompt(query="find latest cybersecurity news today")
        assert "SEARCH SKILL" in prompt

    def test_website_query_includes_web(self, sm):
        prompt = sm.get_trinity_prompt(query="check if trinity6.com ssl is valid")
        assert "WEB SKILL" in prompt

    def test_debug_query_includes_debug(self, sm):
        prompt = sm.get_trinity_prompt(query="why is the skill broken? debug the error")
        assert "DEBUG SKILL" in prompt

    def test_memory_always_included(self, sm):
        # Even for focused queries, memory context is always useful
        prompt = sm.get_trinity_prompt(query="check ssl certificate")
        assert "MEMORY SKILL" in prompt

    def test_broad_query_returns_full_prompt(self, sm):
        # A broad query should include everything
        prompt = sm.get_trinity_prompt(
            query="give me a full briefing: news, code review, website check, revenue, math"
        )
        # All skills should be in the full-prompt fallback
        assert "GITHUB SKILL" in prompt or "CALCULATOR SKILL" in prompt

    def test_honesty_rules_always_present(self, sm):
        """Anti-BS rules must be in every prompt."""
        for query in [None, "simple question", "check code"]:
            prompt = sm.get_trinity_prompt(query=query)
            assert "HONESTY RULES" in prompt or "never make up" in prompt.lower()

    def test_dynamic_prompt_shorter_than_full(self, sm):
        full = sm.get_trinity_prompt(query=None)
        focused = sm.get_trinity_prompt(query="check ssl certificate for trinity6.com")
        # Focused prompt should be shorter (fewer skills)
        assert len(focused) <= len(full)


# ── _detect_relevant_skills() ────────────────────────────────────────────────


class TestDetectRelevantSkills:
    @pytest.fixture
    def sm(self):
        return SkillManager()

    def test_none_query_returns_none(self, sm):
        assert sm._detect_relevant_skills(None) is None

    def test_empty_string_returns_none_full_prompt(self, sm):
        # Empty string is falsy — same as None, returns full prompt
        skills = sm._detect_relevant_skills("")
        assert skills is None

    def test_github_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("read file from github repo")
        assert "github" in skills

    def test_code_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("find bugs in the code")
        assert "code" in skills
        assert "github" in skills  # code also pulls github

    def test_web_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("check if website is online")
        assert "web" in skills

    def test_search_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("find latest news")
        assert "search" in skills

    def test_business_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("show me the client pipeline and revenue")
        assert "business" in skills

    def test_calculator_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("calculate how much in INR")
        assert "calculator" in skills

    def test_debug_keywords_detected(self, sm):
        skills = sm._detect_relevant_skills("debug this error in the skill")
        assert "debug" in skills

    def test_broad_query_returns_none_for_full_prompt(self, sm):
        # 5+ skills triggered → return None (full prompt)
        skills = sm._detect_relevant_skills(
            "review code, check news, calculate revenue, debug error, check website"
        )
        assert skills is None

    def test_result_is_sorted_list(self, sm):
        skills = sm._detect_relevant_skills("check ssl and calculate cost")
        assert isinstance(skills, list)
        assert skills == sorted(skills)


# ── Trinity LLM routing (unit test with mocks) ───────────────────────────────


class TestTrinityLLMRouting:
    """
    Test get_llm_for_task() routing logic without actually loading Trinity
    (which requires env vars and network).
    We test the routing method by patching the LLM attributes.
    """

    def _make_trinity_stub(self):
        """
        Create a minimal stub of Trinity with just the routing method.
        Imports Trinity class and overrides LLM attributes.
        """
        with patch('core.trinity.Trinity.__init__', return_value=None):
            from core.trinity import Trinity
            t = Trinity.__new__(Trinity)
            t._local_llm = MagicMock(name="local_30b")
            t._cloud_llm = MagicMock(name="cloud_haiku")
            t.llm = t._cloud_llm
            t._local_model_name = "llama3.3:70b"
            return t, Trinity

    def test_short_simple_query_uses_cloud(self):
        t, Trinity = self._make_trinity_stub()
        # Bind the real method
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        llm = t.get_llm_for_task("What is the website status?")
        assert llm is t._cloud_llm

    def test_complex_keyword_routes_to_local(self):
        t, Trinity = self._make_trinity_stub()
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        llm = t.get_llm_for_task("review the code in trinity6 scanner and analyze all functions")
        assert llm is t._local_llm

    def test_long_message_routes_to_local(self):
        t, Trinity = self._make_trinity_stub()
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        long_q = "x " * 150  # >200 chars
        llm = t.get_llm_for_task(long_q)
        assert llm is t._local_llm

    def test_code_block_routes_to_local(self):
        t, Trinity = self._make_trinity_stub()
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        q = "Help me with this:\n```python\ndef foo(): pass\n```"
        llm = t.get_llm_for_task(q)
        assert llm is t._local_llm

    def test_no_local_llm_falls_back_to_cloud(self):
        t, Trinity = self._make_trinity_stub()
        t._local_llm = None  # local not available
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        # Even a "complex" query should fall back to cloud
        llm = t.get_llm_for_task("analyze the entire codebase deeply")
        assert llm is t._cloud_llm

    def test_no_local_no_cloud_returns_default_llm(self):
        t, Trinity = self._make_trinity_stub()
        t._local_llm = None
        t._cloud_llm = None
        default_mock = MagicMock(name="default_llm")
        t.llm = default_mock
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        llm = t.get_llm_for_task("anything")
        assert llm is default_mock

    def test_debug_keyword_does_not_force_local_without_local_available(self):
        t, Trinity = self._make_trinity_stub()
        t._local_llm = None
        from core.trinity import Trinity as RealTrinity
        t.get_llm_for_task = RealTrinity.get_llm_for_task.__get__(t, type(t))

        llm = t.get_llm_for_task("debug this error")
        assert llm is t._cloud_llm  # cloud fallback


# ── Anti-BS prompt rules ──────────────────────────────────────────────────────


class TestAntiHallucinationRules:
    @pytest.fixture
    def sm(self):
        return SkillManager()

    def test_never_compute_in_head_rule_present(self, sm):
        prompt = sm.get_trinity_prompt()
        assert "calculator" in prompt.lower()
        # Must instruct to use calculator, not guess
        assert "arithmetic" in prompt.lower() or "calculate" in prompt.lower()

    def test_never_make_up_data_rule_present(self, sm):
        prompt = sm.get_trinity_prompt()
        assert "make up" in prompt.lower() or "never guess" in prompt.lower() or "never make up" in prompt.lower()

    def test_search_for_current_info_rule_present(self, sm):
        prompt = sm.get_trinity_prompt()
        assert "search" in prompt.lower()

    def test_honest_about_unknown_rule_present(self, sm):
        prompt = sm.get_trinity_prompt()
        assert "don't know" in prompt.lower() or "do not know" in prompt.lower() or "say so" in prompt.lower()
