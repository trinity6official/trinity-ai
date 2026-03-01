"""
Tests for core/decisions.py — TrinityDecisions

The decision engine is the most critical safety layer in Trinity.
It controls which actions Trinity executes autonomously vs. which
require David's explicit approval. Bugs here could cause unintended
autonomous behaviour (spending money, contacting clients, etc.).
"""
import pytest
from unittest.mock import MagicMock, patch, call


def make_decisions():
    """Factory: return a TrinityDecisions instance with a mock memory."""
    from core.decisions import TrinityDecisions

    mock_memory = MagicMock()
    mock_memory.brain = {
        "david": {},
        "company": {"revenue": 0, "current_phase": "Phase 1"},
        "hardware": {},
    }
    mock_memory.get_days_alive.return_value = 0

    return TrinityDecisions(
        memory=mock_memory,
        telegram_token="fake_token",
        chat_id="fake_chat_id",
    )


# ── can_act_alone ─────────────────────────────────────────────────


class TestCanActAlone:
    def test_known_safe_actions_return_true(self):
        d = make_decisions()
        safe = [
            "daily_content_posting",
            "morning_briefing",
            "evening_checkin",
            "monitoring_checks",
            "alert_sending",
            "memory_updates",
            "self_improvement",
            "health_checks",
            "weekly_report",
        ]
        for action in safe:
            assert d.can_act_alone(action) is True, f"Expected True for {action}"

    def test_unknown_action_returns_false(self):
        d = make_decisions()
        assert d.can_act_alone("unknown_action") is False

    def test_approval_required_actions_not_in_alone(self):
        d = make_decisions()
        risky = ["spending_money", "deleting_files", "contacting_clients"]
        for action in risky:
            assert d.can_act_alone(action) is False, f"Expected False for {action}"


# ── needs_approval ────────────────────────────────────────────────


class TestNeedsApproval:
    def test_known_approval_actions_return_true(self):
        d = make_decisions()
        approval_required = [
            "spending_money",
            "contacting_clients",
            "major_product_changes",
            "deleting_files",
            "sending_external_emails",
            "publishing_to_website",
            "anything_uncertain",
        ]
        for action in approval_required:
            assert d.needs_approval(action) is True, f"Expected True for {action}"

    def test_safe_action_not_in_approval_list(self):
        d = make_decisions()
        assert d.needs_approval("morning_briefing") is False

    def test_unknown_action_returns_false(self):
        d = make_decisions()
        assert d.needs_approval("completely_made_up") is False


# ── never_do ──────────────────────────────────────────────────────


class TestNeverDo:
    def test_forbidden_actions_return_true(self):
        d = make_decisions()
        forbidden = [
            "spend_money_without_approval",
            "contact_external_people_alone",
            "make_irreversible_changes",
            "ignore_davids_wellbeing",
            "delete_critical_files",
            "share_private_information",
        ]
        for action in forbidden:
            assert d.never_do(action) is True, f"Expected True for {action}"

    def test_safe_action_not_forbidden(self):
        d = make_decisions()
        assert d.never_do("morning_briefing") is False

    def test_no_overlap_between_alone_and_never_do(self):
        """Actions that Trinity can do alone must not appear in the never_do list."""
        d = make_decisions()
        alone_actions = [
            "daily_content_posting",
            "morning_briefing",
            "evening_checkin",
            "monitoring_checks",
            "alert_sending",
            "memory_updates",
            "self_improvement",
            "health_checks",
            "weekly_report",
        ]
        for action in alone_actions:
            assert d.never_do(action) is False, (
                f"'{action}' is in can_act_alone but also flagged by never_do"
            )


# ── request_approval / check_approval_response ───────────────────


class TestApprovalSystem:
    def test_approval_id_has_expected_prefix(self):
        d = make_decisions()
        with patch.object(d, "send_telegram"):
            approval_id = d.request_approval("spend", "desc", "high", cost="$50")
        assert approval_id.startswith("approval_")

    def test_pending_approval_stored(self):
        d = make_decisions()
        with patch.object(d, "send_telegram"):
            d.request_approval("spend", "desc", "high")
        assert len(d.pending_approvals) == 1
        entry = d.pending_approvals[0]
        assert entry["action"] == "spend"
        assert entry["status"] == "pending"

    def test_approval_with_cost_included(self):
        d = make_decisions()
        with patch.object(d, "send_telegram") as mock_tg:
            d.request_approval("buy_server", "New server", "high", cost="$200")
        sent_message = mock_tg.call_args[0][0]
        assert "$200" in sent_message

    def test_check_approval_pending(self):
        d = make_decisions()
        with patch.object(d, "send_telegram"):
            aid = d.request_approval("action", "desc", "low")
        assert d.check_approval_response(aid) == "pending"

    def test_check_approval_not_found(self):
        d = make_decisions()
        assert d.check_approval_response("nonexistent_id") == "not_found"

    def test_multiple_approvals_tracked_independently(self):
        d = make_decisions()
        with patch.object(d, "send_telegram"):
            aid1 = d.request_approval("action1", "desc1", "low")
            aid2 = d.request_approval("action2", "desc2", "high")
        assert d.check_approval_response(aid1) == "pending"
        assert d.check_approval_response(aid2) == "pending"
        assert aid1 != aid2

    def test_memory_record_decision_called(self):
        d = make_decisions()
        with patch.object(d, "send_telegram"):
            d.request_approval("test_action", "desc", "low")
        d.memory.record_decision.assert_called_once()


# ── generate_daily_recommendation ────────────────────────────────


class TestDailyRecommendations:
    def test_critical_website_triggers_urgent(self):
        d = make_decisions()
        recs = d.generate_daily_recommendation(
            health_summary={"overall": "critical"}, github_data={}
        )
        assert any("URGENT" in r for r in recs)

    def test_failed_workflow_included_in_recs(self):
        d = make_decisions()
        github_data = {
            "trinity-ai": {
                "recent_workflows": [{"conclusion": "failure"}]
            }
        }
        recs = d.generate_daily_recommendation(
            health_summary={}, github_data=github_data
        )
        assert any("trinity-ai" in r for r in recs)

    def test_multiple_failed_repos_all_mentioned(self):
        d = make_decisions()
        github_data = {
            "repo-a": {"recent_workflows": [{"conclusion": "failure"}]},
            "repo-b": {"recent_workflows": [{"conclusion": "failure"}]},
        }
        recs = d.generate_daily_recommendation(
            health_summary={}, github_data=github_data
        )
        combined = " ".join(recs)
        assert "repo-a" in combined
        assert "repo-b" in combined

    def test_zero_revenue_triggers_client_outreach_rec(self):
        d = make_decisions()
        d.memory.brain["company"]["revenue"] = 0
        recs = d.generate_daily_recommendation(
            health_summary={}, github_data={}
        )
        assert any(
            "client" in r.lower() or "revenue" in r.lower() for r in recs
        )

    def test_no_issues_returns_fallback_rec(self):
        d = make_decisions()
        d.memory.brain["company"]["revenue"] = 5000
        d.memory.brain["company"]["current_phase"] = "Phase 1"
        recs = d.generate_daily_recommendation(
            health_summary={"overall": "healthy"}, github_data={}
        )
        assert len(recs) >= 1  # Always returns at least one recommendation

    def test_hardware_arriving_triggers_ubuntu_rec(self):
        d = make_decisions()
        d.memory.brain["hardware"] = {"desktop": {"status": "arriving_soon"}}
        d.memory.brain["company"]["revenue"] = 5000  # suppress revenue rec
        recs = d.generate_daily_recommendation(
            health_summary={"overall": "healthy"}, github_data={}
        )
        combined = " ".join(recs).lower()
        assert "hardware" in combined or "ubuntu" in combined

    def test_phase_2_complete_triggers_phase3_rec(self):
        d = make_decisions()
        d.memory.brain["company"]["current_phase"] = "Phase 2"
        d.memory.brain["company"]["revenue"] = 5000  # suppress revenue rec
        recs = d.generate_daily_recommendation(
            health_summary={"overall": "healthy"}, github_data={}
        )
        combined = " ".join(recs).lower()
        assert "phase 3" in combined or "phase3" in combined or "client" in combined
