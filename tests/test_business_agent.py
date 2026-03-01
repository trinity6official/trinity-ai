"""
Tests for agents/business_agent.py — BusinessAgent

BusinessAgent computes health scores and generates alerts that drive
Trinity's recommendations to David. Wrong health scores mean wrong
priorities. Missing alerts mean missed business risks.
"""
import pytest
from unittest.mock import MagicMock
from agents.business_agent import BusinessAgent


def make_agent(days_building=0, revenue=0, clients=None, phase="Phase 1"):
    """Factory: return a BusinessAgent with a mock memory."""
    mock_memory = MagicMock()
    mock_memory.brain = {
        "company": {
            "days_building": days_building,
            "revenue": revenue,
            "clients": clients or [],
            "next_milestone": "Get first client",
            "current_phase": phase,
        },
        "david": {"financial_goals": []},
    }
    return BusinessAgent(memory=mock_memory)


# ── get_business_status ───────────────────────────────────────────


class TestGetBusinessStatus:
    def test_returns_empty_dict_when_no_memory(self):
        agent = BusinessAgent(memory=None)
        assert agent.get_business_status() == {}

    def test_returns_timestamp(self):
        agent = make_agent()
        result = agent.get_business_status()
        assert "timestamp" in result

    def test_full_health_score_early_stage_no_clients(self):
        # 0 days, 0 revenue, 0 clients → only -10 for no clients
        agent = make_agent(days_building=0, revenue=0, clients=[])
        result = agent.get_business_status()
        assert result["health_score"] == 90

    def test_health_penalty_after_30_days_no_revenue(self):
        agent = make_agent(days_building=31, revenue=0, clients=[])
        result = agent.get_business_status()
        # -20 for no revenue after 30 days, -10 for no clients
        assert result["health_score"] == 70

    def test_no_revenue_alert_after_30_days(self):
        agent = make_agent(days_building=31, revenue=0)
        result = agent.get_business_status()
        assert any(
            "revenue" in a.lower() or "client" in a.lower()
            for a in result["alerts"]
        )

    def test_no_revenue_alert_not_triggered_before_30_days(self):
        agent = make_agent(days_building=20, revenue=0)
        result = agent.get_business_status()
        # Only the "no clients" alert should fire, not the revenue one
        revenue_alerts = [
            a for a in result["alerts"]
            if "revenue" in a.lower() and "30" in a
        ]
        assert len(revenue_alerts) == 0

    def test_no_clients_alert_generated(self):
        agent = make_agent(clients=[])
        result = agent.get_business_status()
        assert any("client" in a.lower() for a in result["alerts"])

    def test_no_clients_alert_absent_when_clients_exist(self):
        agent = make_agent(clients=["Acme Corp", "Beta Ltd"])
        result = agent.get_business_status()
        # The "no clients" specific alert should not fire
        no_client_alerts = [
            a for a in result["alerts"]
            if "no clients" in a.lower()
        ]
        assert len(no_client_alerts) == 0

    def test_total_clients_count(self):
        agent = make_agent(clients=["A", "B", "C"])
        result = agent.get_business_status()
        assert result["total_clients"] == 3

    def test_days_building_returned(self):
        agent = make_agent(days_building=45)
        result = agent.get_business_status()
        assert result["days_building"] == 45

    def test_revenue_returned(self):
        agent = make_agent(revenue=5000)
        result = agent.get_business_status()
        assert result["revenue"] == 5000

    def test_health_score_not_penalised_when_revenue_exists(self):
        agent = make_agent(days_building=60, revenue=1000, clients=["A"])
        result = agent.get_business_status()
        # Revenue > 0 and clients exist → no penalties
        assert result["health_score"] == 100

    def test_health_score_never_exceeds_100(self):
        agent = make_agent(days_building=0, revenue=99999, clients=["A", "B"])
        result = agent.get_business_status()
        assert result["health_score"] <= 100
