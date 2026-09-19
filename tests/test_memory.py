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
    """Return a path inside a fresh temp directory for each test."""
    return str(tmp_path / "memory" / "trinity_brain.json")


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

    def test_save_uses_sqlite_state_instead_of_recreating_legacy_json(self, tmp_path):
        from core.memory import TrinityMemory
        deep_path = str(tmp_path / "a" / "b" / "c" / "brain.json")
        m = TrinityMemory(brain_file=deep_path)
        m.brain["key"] = "val"
        m.save()
        assert not os.path.exists(deep_path)
        assert m.store.load_state(m.STATE_NAMESPACE)["key"] == "val"

    def test_save_with_bare_filename_does_not_raise(self, tmp_path, monkeypatch):
        """A bare migration filename does not become an active state file."""
        from core.memory import TrinityMemory
        monkeypatch.chdir(tmp_path)
        m = TrinityMemory(brain_file="bare_brain.json")
        m.brain["key"] = "val"
        m.save()
        assert not (tmp_path / "bare_brain.json").exists()
        assert (tmp_path / "trinity_memory.db").exists()

    def test_legacy_json_cannot_reclaim_ownership_after_sqlite_migration(self, tmp_path):
        from core.memory import TrinityMemory

        legacy = tmp_path / "memory" / "trinity_brain.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({"company": {"current_phase": "legacy"}}))

        first = TrinityMemory(brain_file=str(legacy))
        first.update_company("current_phase", "consolidated")

        legacy.write_text(json.dumps({"company": {"current_phase": "stale-json"}}))
        reopened = TrinityMemory(brain_file=str(legacy))

        assert reopened.brain["company"]["current_phase"] == "consolidated"


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


# ── cross-method history initialisation ──────────────────────────


class TestCrossMethodHistoryInit:
    """
    Regression tests for the KeyError bug that occurred when methods
    sharing the 'history' key were called in different orders.

    Previously, each method initialised history with only its own subkey
    (e.g. record_decision set {'decisions_made': []}). A subsequent call
    to add_alert would see history already present and try to append to
    history['alerts_sent'] — raising KeyError because alerts_sent was
    never created.
    """

    def test_add_alert_after_record_decision_does_not_raise(self, memory):
        memory.record_decision("Deploy", "Success")
        memory.add_alert("ssl", "SSL cert expiring")   # must not KeyError
        assert len(memory.brain["history"]["alerts_sent"]) == 1

    def test_record_decision_after_add_alert_does_not_raise(self, memory):
        memory.add_alert("ssl", "SSL cert expiring")
        memory.record_decision("Deploy", "Success")    # must not KeyError
        assert len(memory.brain["history"]["decisions_made"]) == 1

    def test_add_alert_after_add_daily_log_does_not_raise(self, memory):
        memory.add_daily_log("Daily log entry")
        memory.add_alert("disk_full", "Disk 95% full")  # must not KeyError
        assert len(memory.brain["history"]["alerts_sent"]) == 1

    def test_all_three_methods_coexist_in_history(self, memory):
        memory.record_decision("Deploy", "Success")
        memory.add_alert("ssl", "Expiring")
        memory.add_daily_log("Logged something")
        h = memory.brain["history"]
        assert len(h["decisions_made"]) == 1
        assert len(h["alerts_sent"]) == 1
        assert len(h["daily_logs"]) == 1


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

# ── Memory Vault + SQLite ─────────────────────────────────────────

class TestDurableMemoryVault:
    def test_remember_and_recall_roundtrip(self, memory):
        memory.remember("Local AI is Trinity's core architecture", category="architecture", importance=0.9)
        results = memory.recall("local AI architecture")
        assert results
        assert "Local AI" in results[0].content

    def test_deduplicates_same_memory(self, memory):
        first = memory.remember("Use local models", category="architecture", importance=0.7)
        second = memory.remember("Use local models", category="architecture", importance=0.9)
        assert first == second
        assert len(memory.recall("local models")) == 1

    def test_high_importance_memory_written_to_markdown(self, memory, tmp_path):
        memory.remember("A durable architecture decision", kind="decision", category="architecture", importance=0.9)
        vault_file = tmp_path / "memory" / "vault" / "decisions" / "architecture.md"
        assert vault_file.exists()
        assert "durable architecture decision" in vault_file.read_text()

    def test_daily_log_written_to_markdown_vault(self, memory, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Fixture store is anchored to tmp_path/memory even after cwd changes.
        memory.add_daily_log("Built the memory vault")
        daily_files = list((tmp_path / "memory" / "vault" / "daily").glob("*.md"))
        assert daily_files
        assert "Built the memory vault" in daily_files[0].read_text()

    def test_legacy_brain_import_is_idempotent(self, tmp_path):
        brain_file = tmp_path / "memory" / "trinity_brain.json"
        brain_file.parent.mkdir(parents=True)
        brain_file.write_text(json.dumps({"identity": {"name": "Trinity"}, "knowledge": {"what_works": ["Local first"]}}))
        from core.memory import TrinityMemory
        first = TrinityMemory(brain_file=str(brain_file))
        initial = len(first.recent_memories(100))
        second = TrinityMemory(brain_file=str(brain_file))
        assert len(second.recent_memories(100)) == initial


# ── objectives / current focus ───────────────────────────────────


class TestObjectivesAndFocus:
    def test_objective_persists_across_reload(self, memory, tmp_brain_path):
        from core.memory import TrinityMemory

        created = memory.create_objective(
            "Prepare for a personal trip",
            success_criteria=["Bookings complete", "Documents ready"],
            importance=0.8,
            priority=0.9,
            make_focus=True,
        )

        reloaded = TrinityMemory(brain_file=tmp_brain_path)
        objective = reloaded.get_objective(created["id"])
        assert objective is not None
        assert objective["title"] == "Prepare for a personal trip"
        assert objective["success_criteria"] == [
            "Bookings complete",
            "Documents ready",
        ]
        assert reloaded.get_current_focus()["id"] == created["id"]

    def test_changing_focus_preserves_previous_objective(self, memory):
        first = memory.create_objective("First priority", make_focus=True)
        second = memory.create_objective("Different priority")

        memory.set_current_focus(second["id"])

        assert memory.get_current_focus()["id"] == second["id"]
        assert memory.get_objective(first["id"])["status"] == "active"

    def test_pausing_current_focus_clears_focus_but_keeps_history(self, memory):
        objective = memory.create_objective("Temporary focus", make_focus=True)

        updated = memory.set_objective_status(
            objective["id"],
            "paused",
            reason="David changed focus",
        )

        assert memory.get_current_focus() is None
        assert memory.get_objective(objective["id"])["status"] == "paused"
        assert updated["status_history"][-1]["reason"] == "David changed focus"

    def test_completed_objective_is_retained_and_not_open_context(self, memory):
        objective = memory.create_objective("Finish setup", make_focus=True)
        memory.set_objective_status(
            objective["id"],
            "completed",
            reason="Done",
        )

        stored = memory.get_objective(objective["id"])
        context = memory.get_objective_context()

        assert stored["status"] == "completed"
        assert stored["progress"] == 1.0
        assert context["current_focus"] is None
        assert all(
            item["id"] != objective["id"]
            for item in context["other_open_objectives"]
        )

    def test_focus_requires_active_or_blocked_objective(self, memory):
        objective = memory.create_objective("Later")
        memory.set_objective_status(objective["id"], "paused")

        with pytest.raises(ValueError, match="active or blocked"):
            memory.set_current_focus(objective["id"])

    def test_priority_changes_without_changing_importance(self, memory):
        objective = memory.create_objective(
            "Long-term objective",
            importance=0.9,
            priority=0.2,
        )

        updated = memory.update_objective_priority(objective["id"], 0.8)

        assert updated["priority"] == 0.8
        assert updated["importance"] == 0.9

    def test_full_context_contains_only_bounded_objective_view(self, memory):
        focus = memory.create_objective("Current focus", make_focus=True)
        for index in range(7):
            memory.create_objective(
                f"Open objective {index}",
                priority=index / 10,
            )

        parsed = json.loads(memory.get_full_context())
        objective_context = parsed["objectives"]

        assert objective_context["current_focus"]["id"] == focus["id"]
        assert len(objective_context["other_open_objectives"]) == 5

    def test_superseded_objective_points_to_replacement(self, memory):
        old = memory.create_objective("Build custom integration")
        replacement = memory.create_objective("Use existing MCP integration")

        updated = memory.set_objective_status(
            old["id"],
            "superseded",
            reason="Existing capability already solves it",
            superseded_by=replacement["id"],
        )

        assert updated["superseded_by"] == replacement["id"]
        assert memory.get_objective(old["id"])["status"] == "superseded"
