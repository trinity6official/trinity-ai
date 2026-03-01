"""
Tests for core/memory.py — TrinityMemory

The memory layer is Trinity's persistence backbone. Bugs here mean
lost decisions, lost alerts, incorrect wellbeing scores, or data
corruption across runs. All methods here are pure filesystem I/O
with no external network dependencies — ideal for unit testing.
"""
import json
import os
import tempfile
import shutil

import pytest


@pytest.fixture
def tmp_brain_path(tmp_path):
    """Return a root-level path matching the unified brain file location."""
    return str(tmp_path / "trinity_brain.json")


@pytest.fixture
def memory(tmp_brain_path):
    from core.memory import TrinityMemory
    return TrinityMemory(brain_file=tmp_brain_path)


# ── load ──────────────────────────────────────────────────────────


class TestLoad:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        from core.memory import TrinityMemory
        m = TrinityMemory(brain_file=str(tmp_path / "nonexistent.json"))
        assert m.brain == {}

    def test_corrupted_json_returns_empty_dict(self, tmp_path):
        brain_file = tmp_path / "brain.json"
        brain_file.write_text("{invalid json }")
        from core.memory import TrinityMemory
        m = TrinityMemory(brain_file=str(brain_file))
        assert m.brain == {}

    def test_valid_json_loads_correctly(self, tmp_path):
        brain_file = tmp_path / "brain.json"
        data = {"identity": {"name": "Trinity"}}
        brain_file.write_text(json.dumps(data))
        from core.memory import TrinityMemory
        m = TrinityMemory(brain_file=str(brain_file))
        assert m.brain["identity"]["name"] == "Trinity"


# ── save / roundtrip ──────────────────────────────────────────────


class TestSave:
    def test_save_and_reload_roundtrip(self, memory, tmp_brain_path):
        from core.memory import TrinityMemory
        memory.brain["test_key"] = "test_value"
        memory.save()
        reloaded = TrinityMemory(brain_file=tmp_brain_path)
        assert reloaded.brain.get("test_key") == "test_value"

    def test_save_creates_parent_directory(self, tmp_path):
        from core.memory import TrinityMemory
        deep_path = str(tmp_path / "a" / "b" / "c" / "brain.json")
        m = TrinityMemory(brain_file=deep_path)
        m.brain["key"] = "val"
        m.save()
        assert os.path.exists(deep_path)


# ── update_last_wakeup ────────────────────────────────────────────


class TestUpdateLastWakeup:
    def test_creates_identity_if_missing(self, memory):
        memory.update_last_wakeup()
        assert "identity" in memory.brain

    def test_days_alive_starts_at_one(self, memory):
        memory.update_last_wakeup()
        assert memory.brain["identity"]["days_alive"] == 1

    def test_days_alive_increments_each_call(self, memory):
        memory.update_last_wakeup()
        memory.update_last_wakeup()
        memory.update_last_wakeup()
        assert memory.brain["identity"]["days_alive"] == 3

    def test_last_wakeup_is_set(self, memory):
        memory.update_last_wakeup()
        assert memory.brain["identity"]["last_wakeup"] is not None


# ── alerts ────────────────────────────────────────────────────────


class TestAlerts:
    def test_add_alert_appears_in_history(self, memory):
        memory.add_alert("ssl_expiry", "SSL cert expiring")
        assert len(memory.brain["history"]["alerts_sent"]) == 1

    def test_add_alert_appears_in_monitoring(self, memory):
        memory.add_alert("ssl_expiry", "SSL cert expiring")
        assert len(memory.brain["monitoring"]["alerts_active"]) == 1

    def test_alert_severity_stored(self, memory):
        memory.add_alert("disk_full", "Disk 95% full", severity="high")
        entry = memory.brain["history"]["alerts_sent"][0]
        assert entry["severity"] == "high"

    def test_clear_alert_removes_target_type(self, memory):
        memory.add_alert("ssl_expiry", "SSL expiring")
        memory.add_alert("disk_full", "Disk full")
        memory.clear_alert("ssl_expiry")
        active_types = [
            a["type"] for a in memory.brain["monitoring"]["alerts_active"]
        ]
        assert "ssl_expiry" not in active_types
        assert "disk_full" in active_types

    def test_clear_alert_on_empty_brain_does_not_raise(self, memory):
        memory.clear_alert("nonexistent_type")  # Must not raise

    def test_clear_nonexistent_type_leaves_others_intact(self, memory):
        memory.add_alert("real_alert", "msg")
        memory.clear_alert("ghost_alert")
        assert len(memory.brain["monitoring"]["alerts_active"]) == 1

    def test_get_active_alerts_empty_brain(self, memory):
        assert memory.get_active_alerts() == []

    def test_get_active_alerts_returns_list(self, memory):
        memory.add_alert("type1", "msg1")
        memory.add_alert("type2", "msg2")
        result = memory.get_active_alerts()
        assert len(result) == 2


# ── record_decision ───────────────────────────────────────────────


class TestRecordDecision:
    def test_decision_stored_with_correct_fields(self, memory):
        memory.record_decision("Deploy v2", "Success")
        entries = memory.brain["history"]["decisions_made"]
        assert len(entries) == 1
        assert entries[0]["decision"] == "Deploy v2"
        assert entries[0]["outcome"] == "Success"
        assert "timestamp" in entries[0]

    def test_multiple_decisions_all_stored(self, memory):
        memory.record_decision("Deploy v2", "Success")
        memory.record_decision("Send briefing", "Sent")
        assert len(memory.brain["history"]["decisions_made"]) == 2


# ── learn ─────────────────────────────────────────────────────────


class TestLearn:
    def test_what_works_stored(self, memory):
        memory.learn("what_works", "Daily standups improve focus")
        assert "Daily standups improve focus" in memory.brain["knowledge"]["what_works"]

    def test_what_works_deduplicates(self, memory):
        memory.learn("what_works", "Same insight")
        memory.learn("what_works", "Same insight")
        assert memory.brain["knowledge"]["what_works"].count("Same insight") == 1

    def test_what_doesnt_deduplicates(self, memory):
        memory.learn("what_doesnt", "Spam outreach doesn't work")
        memory.learn("what_doesnt", "Spam outreach doesn't work")
        assert memory.brain["knowledge"]["what_doesnt"].count(
            "Spam outreach doesn't work"
        ) == 1

    def test_pattern_allows_duplicates(self, memory):
        """Patterns are timestamped observations — duplicates are valid."""
        memory.learn("pattern", "David active at 9am")
        memory.learn("pattern", "David active at 9am")
        assert len(memory.brain["knowledge"]["patterns_noticed"]) == 2

    def test_learning_interactions_increment(self, memory):
        memory.learn("what_works", "insight A")
        memory.learn("what_doesnt", "insight B")
        assert memory.brain["learning"]["total_interactions"] == 2


# ── wellbeing ─────────────────────────────────────────────────────


class TestWellbeing:
    def test_wellbeing_score_set(self, memory):
        memory.update_wellbeing(80)
        assert memory.brain["david"]["wellbeing_score"] == 80

    def test_note_appended_when_provided(self, memory):
        memory.update_wellbeing(75, note="Working too late")
        assert len(memory.brain["david"]["notes"]) == 1
        assert memory.brain["david"]["notes"][0]["note"] == "Working too late"

    def test_multiple_notes_accumulate(self, memory):
        memory.update_wellbeing(80, note="Note A")
        memory.update_wellbeing(70, note="Note B")
        assert len(memory.brain["david"]["notes"]) == 2

    def test_wellbeing_no_note_does_not_create_notes_key(self, memory):
        memory.update_wellbeing(90)
        assert "notes" not in memory.brain.get("david", {})


# ── conversations ─────────────────────────────────────────────────


class TestConversations:
    def test_conversation_stored(self, memory):
        memory.add_conversation("user", "Hello Trinity")
        convos = memory.brain["history"]["conversations"]
        assert len(convos) == 1
        assert convos[0]["role"] == "user"
        assert convos[0]["message"] == "Hello Trinity"

    def test_conversation_capped_at_100(self, memory):
        for i in range(110):
            memory.add_conversation("user", f"Message {i}")
        convos = memory.brain["history"]["conversations"]
        assert len(convos) == 100

    def test_most_recent_messages_kept_after_cap(self, memory):
        for i in range(110):
            memory.add_conversation("user", f"Message {i}")
        last_message = memory.brain["history"]["conversations"][-1]["message"]
        assert last_message == "Message 109"


# ── helpers ───────────────────────────────────────────────────────


class TestHelpers:
    def test_get_days_alive_empty_brain(self, memory):
        assert memory.get_days_alive() == 0

    def test_get_days_alive_after_wakeup(self, memory):
        memory.update_last_wakeup()
        assert memory.get_days_alive() == 1

    def test_get_company_summary_defaults(self, memory):
        summary = memory.get_company_summary()
        assert summary["revenue"] == 0
        assert summary["clients"] == 0

    def test_get_david_summary_defaults(self, memory):
        summary = memory.get_david_summary()
        assert summary["wellbeing_score"] == 100

    def test_get_recent_logs_empty(self, memory):
        assert memory.get_recent_logs() == []

    def test_get_full_context_returns_json_string(self, memory):
        ctx = memory.get_full_context()
        parsed = json.loads(ctx)
        assert "david" in parsed
        assert "company" in parsed
