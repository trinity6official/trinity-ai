"""
Real tests for permanent memory (pin_memory / get_pinned) in memory_skill.py

Tests use a temp file so they don't corrupt the real brain.
"""
import json
import os
import tempfile
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.memory_skill import MemorySkill


@pytest.fixture
def mem(tmp_path):
    """MemorySkill with a temporary brain file."""
    brain_file = str(tmp_path / "test_brain.json")
    return MemorySkill(brain_file=brain_file)


# ── pin_memory() ──────────────────────────────────────────────────────────────


class TestPinMemory:
    def test_pin_stores_value(self, mem):
        r = mem.pin_memory("first_client", "Acme Corp — ₹5000/month")
        assert r["success"] is True
        assert r["pinned_key"] == "first_client"
        assert r["pinned_value"] == "Acme Corp — ₹5000/month"

    def test_pinned_value_persists_across_instances(self, mem):
        mem.pin_memory("pricing", "₹5000/month for basic plan")
        # Create a new instance pointing at the same file
        mem2 = MemorySkill(brain_file=mem.brain_file)
        r = mem2.get_pinned()
        assert r["success"] is True
        assert "pricing" in r["pinned"]
        assert r["pinned"]["pricing"]["value"] == "₹5000/month for basic plan"

    def test_pin_overwrites_same_key(self, mem):
        mem.pin_memory("target", "first value")
        mem.pin_memory("target", "updated value")
        r = mem.get_pinned()
        assert r["pinned"]["target"]["value"] == "updated value"
        assert r["total_pinned"] == 1  # still one key

    def test_multiple_pins(self, mem):
        mem.pin_memory("client_1", "Acme")
        mem.pin_memory("client_2", "Beta Corp")
        mem.pin_memory("pricing", "₹5000")
        r = mem.get_pinned()
        assert r["total_pinned"] == 3
        assert "client_1" in r["pinned"]
        assert "client_2" in r["pinned"]
        assert "pricing" in r["pinned"]

    def test_pin_timestamp_recorded(self, mem):
        mem.pin_memory("key1", "value1")
        r = mem.get_pinned()
        entry = r["pinned"]["key1"]
        assert "pinned_at" in entry
        assert entry["pinned_at"]  # not empty

    def test_pin_not_in_regular_knowledge(self, mem):
        """Pinned memories live under 'pinned' key, not 'knowledge'."""
        mem.pin_memory("important", "data")
        brain = mem.load_brain()
        assert "pinned" in brain
        knowledge = brain.get("knowledge", {})
        # Should not appear inside knowledge categories
        for cat in knowledge.values():
            if isinstance(cat, list):
                for item in cat:
                    assert "important" not in str(item)


# ── get_pinned() ─────────────────────────────────────────────────────────────


class TestGetPinned:
    def test_empty_pinned_returns_empty_dict(self, mem):
        r = mem.get_pinned()
        assert r["success"] is True
        assert r["pinned"] == {}
        assert r["total_pinned"] == 0

    def test_total_count_accurate(self, mem):
        mem.pin_memory("a", "1")
        mem.pin_memory("b", "2")
        r = mem.get_pinned()
        assert r["total_pinned"] == 2

    def test_execute_routes_pin_memory(self, mem):
        r = mem.execute("pin_memory", {"key": "test", "value": "data"})
        assert r["success"] is True

    def test_execute_routes_get_pinned(self, mem):
        r = mem.execute("get_pinned", {})
        assert r["success"] is True
        assert "pinned" in r

    def test_pin_memory_in_tool_list(self, mem):
        tool_names = {t["name"] for t in mem.get_tools()}
        assert "pin_memory" in tool_names
        assert "get_pinned" in tool_names


# ── Isolation from other memory types ────────────────────────────────────────


class TestPinnedIsolation:
    def test_pinned_survives_update_david(self, mem):
        mem.pin_memory("revenue_goal", "₹10 lakh")
        mem.update_david("mood", "focused")
        r = mem.get_pinned()
        assert "revenue_goal" in r["pinned"]

    def test_pinned_survives_add_log(self, mem):
        mem.pin_memory("client_1", "Acme")
        mem.add_log("Trinity started")
        r = mem.get_pinned()
        assert "client_1" in r["pinned"]

    def test_regular_learn_does_not_affect_pinned(self, mem):
        mem.learn("what_works", "Daily briefing at 6am works well")
        r = mem.get_pinned()
        assert r["total_pinned"] == 0

    def test_pinned_is_separate_brain_section(self, mem):
        mem.pin_memory("key", "value")
        brain = mem.load_brain()
        # 'pinned' is its own top-level section
        assert "pinned" in brain
        assert isinstance(brain["pinned"], dict)
