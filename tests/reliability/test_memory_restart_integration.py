from __future__ import annotations

import pytest

from core.memory_pipeline import ConversationMemoryPipeline
from core.memory_store import MemoryStore


pytestmark = [pytest.mark.contract, pytest.mark.integration]


def test_session_history_and_durable_memory_survive_store_recreation(tmp_path):
    root = tmp_path / "memory"
    first = MemoryStore(root=root)
    pipeline = ConversationMemoryPipeline(first, session_id="restart-contract")

    pipeline.persist(
        "I prefer concise terminal commands",
        "I'll keep terminal instructions concise.",
    )

    second = MemoryStore(root=root)
    sessions = second.search_conversations("concise terminal", limit=5)
    memories = second.search("concise terminal", limit=5)

    assert len(sessions) == 1
    assert sessions[0].session_id == "restart-contract"
    assert sessions[0].user_text == "I prefer concise terminal commands"
    assert any(record.category == "preferences" for record in memories)


def test_transient_session_survives_restart_without_polluting_durable_memory(tmp_path):
    root = tmp_path / "memory"
    first = MemoryStore(root=root)
    pipeline = ConversationMemoryPipeline(first, session_id="transient-contract")

    pipeline.persist("What time did we discuss Atlas?", "We discussed Atlas earlier.")

    second = MemoryStore(root=root)
    sessions = second.search_conversations("Atlas", limit=5)
    durable = second.search("Atlas", limit=5)

    assert len(sessions) == 1
    assert sessions[0].session_id == "transient-contract"
    assert durable == []


@pytest.mark.failure_path
def test_corrupt_legacy_json_is_not_required_for_sqlite_restart_contract(tmp_path):
    """The operational MemoryStore must reopen independently of legacy brain JSON."""
    root = tmp_path / "memory"
    store = MemoryStore(root=root)
    store.remember("Architecture decision survives restart", kind="decision", category="test")
    (root / "trinity_brain.json").write_text("{not-json", encoding="utf-8")

    reopened = MemoryStore(root=root)
    results = reopened.search("Architecture decision", limit=5)

    assert [record.content for record in results] == ["Architecture decision survives restart"]
