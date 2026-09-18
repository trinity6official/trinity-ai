from __future__ import annotations

import json

import pytest

from core.consciousness import Consciousness, empty_brain
from core.memory import MemoryService
from core.memory_pipeline import ConversationMemoryPipeline
from core.memory_store import MemoryStore
from skills.memory_skill import MemorySkill


pytestmark = [pytest.mark.contract, pytest.mark.integration]


def test_runtime_memory_boundary_shares_one_store_across_service_skill_and_sessions(tmp_path):
    root = tmp_path / "memory"
    store = MemoryStore(root=root)
    memory = MemoryService(store=store, brain_file=root / "trinity_brain.json")
    skill = MemorySkill(memory=memory)
    pipeline = ConversationMemoryPipeline(memory.store, session_id="ownership-contract")

    skill.update_company("current_phase", "consolidation")
    pipeline.persist(
        "I prefer concise status updates",
        "I will keep status updates concise.",
    )

    assert skill.memory is memory
    assert skill._session_store() is store
    assert memory.store is store

    reopened_store = MemoryStore(root=root)
    reopened = MemoryService(store=reopened_store, brain_file=root / "trinity_brain.json")
    sessions = reopened_store.search_conversations("concise status", limit=5)
    history = MemorySkill(memory=reopened).search_history("concise status", days=30)

    assert reopened.brain["company"]["current_phase"] == "consolidation"
    assert len(sessions) == 1
    assert sessions[0].session_id == "ownership-contract"
    assert history["total_matches"] == 1


def test_legacy_profile_json_is_migration_input_not_active_owner(tmp_path):
    root = tmp_path / "memory"
    legacy = root / "trinity_brain.json"
    root.mkdir(parents=True)
    legacy.write_text(
        json.dumps({"david": {"preferred_update_style": "legacy"}}),
        encoding="utf-8",
    )

    first = MemoryService(brain_file=legacy)
    first.update_david("preferred_update_style", "concise")

    # A stale compatibility file must not overwrite authoritative SQLite state.
    legacy.write_text(
        json.dumps({"david": {"preferred_update_style": "stale"}}),
        encoding="utf-8",
    )
    reopened = MemoryService(brain_file=legacy)

    assert reopened.brain["david"]["preferred_update_style"] == "concise"


def test_structured_profile_state_does_not_pollute_searchable_durable_memory(tmp_path):
    memory = MemoryService(memory_root=tmp_path / "memory")
    memory.update_company("current_phase", "architecture-consolidation")

    assert memory.store.search("architecture-consolidation") == []


def test_consciousness_runtime_state_migrates_once_then_ignores_stale_legacy_file(tmp_path):
    active = tmp_path / "memory" / "runtime" / "consciousness.json"
    legacy = tmp_path / "trinity_brain.json"
    payload = empty_brain()
    payload["state"]["current_focus"] = "legacy-focus"
    legacy.write_text(json.dumps(payload), encoding="utf-8")

    first = Consciousness(str(active), legacy_brain_path=str(legacy))
    assert first.brain["state"]["current_focus"] == "legacy-focus"
    first.brain["state"]["current_focus"] = "runtime-focus"
    first.save()

    stale = empty_brain()
    stale["state"]["current_focus"] = "stale-legacy"
    legacy.write_text(json.dumps(stale), encoding="utf-8")
    reopened = Consciousness(str(active), legacy_brain_path=str(legacy))

    assert reopened.brain["state"]["current_focus"] == "runtime-focus"
