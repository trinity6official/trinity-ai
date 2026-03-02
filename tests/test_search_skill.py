"""
Real tests for search_skill.py

Tests that verify:
1. The skill structure and routing work correctly
2. DuckDuckGo search is wired up (with network-dependent tests marked)
3. Competitor baseline facts are labeled, not mixed with live data
4. No hardcoded fake "topics" are returned as news
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.search_skill import SearchSkill


@pytest.fixture
def search():
    return SearchSkill()


# ── Tool registration ─────────────────────────────────────────────────────────


class TestToolRegistration:
    def test_all_tools_registered(self, search):
        tools = {t["name"] for t in search.get_tools()}
        expected = {
            "search_web",
            "search_cybersecurity_news",
            "search_cis_updates",
            "find_potential_clients",
            "research_competitor",
            "search_linkedin_prospects",
            "get_market_intelligence",
            "check_source",
        }
        assert expected == tools

    def test_execute_unknown_tool_returns_error(self, search):
        r = search.execute("fly_to_moon", {})
        assert r["success"] is False
        assert "Unknown tool" in r["error"]


# ── search_web() — structure tests (no real network) ─────────────────────────


class TestSearchWebStructure:
    def test_returns_required_keys_on_success(self, search):
        with patch.object(search, '_ddg_search', return_value=[
            {"title": "Fake headline", "url": "example.com", "snippet": "test"}
        ]):
            r = search.search_web("test query")
        assert r["success"] is True
        assert "results" in r
        assert "count" in r
        assert "source" in r
        assert r["source"] == "DuckDuckGo HTML"

    def test_empty_results_are_honest(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.search_web("test query")
        assert r["success"] is True
        assert r["count"] == 0
        assert "No results" in r["note"] or "blocked" in r["note"]

    def test_max_results_param_passed_through(self, search):
        captured = []

        def fake_ddg(query, max_results=5):
            captured.append(max_results)
            return []

        with patch.object(search, '_ddg_search', side_effect=fake_ddg):
            search.search_web("test", max_results=3)

        assert captured[0] == 3


# ── search_cybersecurity_news() — no hardcoded topics ────────────────────────


class TestCybersecurityNews:
    def test_no_hardcoded_topics_list(self, search):
        """
        The old skill had 8 hardcoded topic strings in a 'topics' key.
        The new skill must NOT have this field — all data comes from live scraping.
        """
        with patch.object(search, '_scrape_headlines', return_value=([], 200)):
            with patch.object(search, '_ddg_search', return_value=[]):
                r = search.search_cybersecurity_news()
        assert "topics" not in r, (
            "search_cybersecurity_news() must not return hardcoded 'topics'. "
            "All news must come from live scraping."
        )

    def test_returns_data_freshness_field(self, search):
        with patch.object(search, '_scrape_headlines', return_value=([], 0)):
            with patch.object(search, '_ddg_search', return_value=[]):
                r = search.search_cybersecurity_news()
        assert "data_freshness" in r
        assert "live" in r["data_freshness"].lower()

    def test_sources_checked_field_present(self, search):
        with patch.object(search, '_scrape_headlines', return_value=([], 0)):
            with patch.object(search, '_ddg_search', return_value=[]):
                r = search.search_cybersecurity_news()
        assert "sources_checked" in r
        assert isinstance(r["sources_checked"], list)

    def test_headlines_from_scraping_included(self, search):
        fake_headlines = ["New ransomware targets SMBs", "CISA issues advisory"]

        def fake_scrape(url, selector):
            return fake_headlines, 200

        with patch.object(search, '_scrape_headlines', side_effect=fake_scrape):
            with patch.object(search, '_ddg_search', return_value=[]):
                r = search.search_cybersecurity_news()

        all_h = [h["headline"] for h in r["headlines"]]
        assert "New ransomware targets SMBs" in all_h


# ── research_competitor() — baseline vs live distinction ─────────────────────


class TestResearchCompetitor:
    def test_known_competitor_returns_baseline_and_live(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.research_competitor("nessus")
        assert r["success"] is True
        assert "baseline_facts" in r
        assert "live_search_results" in r
        assert "baseline_disclaimer" in r

    def test_baseline_disclaimer_is_honest(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.research_competitor("qualys")
        assert "verify" in r["baseline_disclaimer"].lower()

    def test_unknown_competitor_still_searches(self, search):
        fake_results = [{"title": "BrandNewScanner review", "url": "x.com", "snippet": ""}]
        with patch.object(search, '_ddg_search', return_value=fake_results):
            r = search.research_competitor("BrandNewScanner")
        assert r["success"] is True
        assert len(r["live_search_results"]) == 1

    def test_known_competitor_case_insensitive(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.research_competitor("NESSUS")
        assert r["baseline_facts"]["name"] == "Nessus by Tenable"

    def test_trinity6_advantages_always_present(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.research_competitor("anything")
        assert "trinity6_advantages" in r
        assert len(r["trinity6_advantages"]) > 0


# ── find_potential_clients() ─────────────────────────────────────────────────


class TestFindPotentialClients:
    def test_returns_web_search_results_field(self, search):
        fake = [{"title": "XYZ IT Chennai", "url": "x.com", "snippet": ""}]
        with patch.object(search, '_ddg_search', return_value=fake):
            r = search.find_potential_clients(location="Chennai")
        assert "web_search_results" in r
        assert r["web_search_results"] == fake

    def test_note_clarifies_linkedin_vs_search(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.find_potential_clients()
        assert "note" in r
        assert "linkedin" in r["note"].lower()

    def test_location_and_industry_in_result(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.find_potential_clients(location="Mumbai", industry="Healthcare")
        assert r["location"] == "Mumbai"
        assert r["industry"] == "Healthcare"


# ── get_market_intelligence() ────────────────────────────────────────────────


class TestMarketIntelligence:
    def test_has_live_and_known_fields(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.get_market_intelligence()
        assert "known_market_figures" in r
        assert "live_global_search" in r
        assert "live_india_search" in r

    def test_known_figures_have_disclaimer(self, search):
        with patch.object(search, '_ddg_search', return_value=[]):
            r = search.get_market_intelligence()
        disclaimer = r["known_market_figures"].get("disclaimer", "")
        assert "verify" in disclaimer.lower()


# ── check_source() ───────────────────────────────────────────────────────────


class TestCheckSource:
    def test_accessible_site_returns_success(self, search):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><head><title>Test Site</title></head></html>"
        mock_resp.elapsed.total_seconds.return_value = 0.1

        with patch("skills.search_skill.requests.get", return_value=mock_resp):
            r = search.check_source("https://example.com")

        assert r["success"] is True
        assert r["accessible"] is True
        assert r["status_code"] == 200

    def test_non_200_returns_not_accessible(self, search):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = ""
        mock_resp.elapsed.total_seconds.return_value = 0.05

        with patch("skills.search_skill.requests.get", return_value=mock_resp):
            r = search.check_source("https://example.com/missing")

        assert r["accessible"] is False

    def test_timeout_returns_error(self, search):
        import requests as req_lib
        with patch("skills.search_skill.requests.get", side_effect=req_lib.Timeout):
            r = search.check_source("https://slow-site.example.com")
        assert r["success"] is False
        assert "Timeout" in r["error"]


# ── search_cis_updates() ─────────────────────────────────────────────────────


class TestCISUpdates:
    def test_returns_trinity6_implements(self, search):
        with patch.object(search, 'check_source', return_value={"accessible": True, "page_title": "CIS"}):
            with patch.object(search, '_ddg_search', return_value=[]):
                r = search.search_cis_updates()
        assert "trinity6_implements" in r
        assert len(r["trinity6_implements"]) > 0

    def test_returns_live_search_results_field(self, search):
        with patch.object(search, 'check_source', return_value={"accessible": False}):
            with patch.object(search, '_ddg_search', return_value=[]):
                r = search.search_cis_updates()
        assert "live_search_results" in r


# ── Network integration (skip if offline) ────────────────────────────────────


@pytest.mark.network
class TestRealNetworkCalls:
    """
    These tests make real HTTP calls to the internet.
    Run with: pytest -m network
    Skip in CI with: pytest -m "not network"
    """

    def test_ddg_search_returns_results(self, search):
        results = search._ddg_search("cybersecurity news", max_results=3)
        # May return 0 results if DuckDuckGo blocks — that's honest, not a bug
        assert isinstance(results, list)
        for r in results:
            assert "title" in r

    def test_check_source_real_url(self, search):
        r = search.check_source("https://thehackernews.com")
        assert "accessible" in r
        assert "status_code" in r
