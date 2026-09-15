from core.memory_consolidation import MemoryConsolidator
from core.memory_store import MemoryStore


def make_consolidator(tmp_path):
    return MemoryConsolidator(MemoryStore(root=tmp_path / "memory"))


def active_contents(consolidator):
    return [record.content for record in consolidator._active_records()]


def test_near_duplicates_are_archived_not_lost(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    store.remember(
        "I prefer concise status updates.",
        kind="semantic",
        category="preferences",
        importance=0.80,
        write_markdown=False,
    )
    store.remember(
        "I prefer concise updates.",
        kind="semantic",
        category="preferences",
        importance=0.78,
        write_markdown=False,
    )

    report = consolidator.consolidate(dry_run=False, similarity_threshold=0.85)

    assert report.duplicate_groups == 1
    assert report.archived_duplicates == 1
    assert len(active_contents(consolidator)) == 1
    assert consolidator.archive_count() == 1


def test_dry_run_does_not_change_memory(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    store.remember("Trinity prefers local inference.", kind="semantic", category="architecture", write_markdown=False)
    store.remember("Trinity prefers local inference", kind="semantic", category="architecture", write_markdown=False)

    report = consolidator.consolidate(dry_run=True, similarity_threshold=0.85)

    assert report.archived_duplicates == 1
    assert len(active_contents(consolidator)) == 2
    assert consolidator.archive_count() == 0


def test_conflicting_version_numbers_are_not_merged(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    store.remember("Phoenix uses Python 3.12", kind="semantic", category="project", write_markdown=False)
    store.remember("Phoenix uses Python 3.13", kind="semantic", category="project", write_markdown=False)

    report = consolidator.consolidate(dry_run=False, similarity_threshold=0.80)

    assert report.archived_duplicates == 0
    assert len(active_contents(consolidator)) == 2


def test_old_low_value_semantic_memory_is_archived(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    memory_id = store.remember(
        "Temporary low-value observation",
        kind="semantic",
        category="general",
        importance=0.10,
        write_markdown=False,
    )
    with store._connection() as conn:
        conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2020-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00", memory_id),
        )

    report = consolidator.consolidate(
        dry_run=False,
        low_value_threshold=0.25,
        low_value_age_days=30,
    )

    assert report.archived_low_value == 1
    assert active_contents(consolidator) == []
    assert consolidator.archive_count() == 1


def test_protected_explicit_memory_is_not_archived_as_low_value(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    memory_id = store.remember(
        "Remember this permanently",
        kind="semantic",
        category="explicit",
        importance=0.05,
        write_markdown=False,
    )
    with store._connection() as conn:
        conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2020-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00", memory_id),
        )

    report = consolidator.consolidate(dry_run=False)

    assert report.archived_low_value == 0
    assert "Remember this permanently" in active_contents(consolidator)


def test_archive_can_be_restored(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    store.remember("I prefer concise status updates.", kind="semantic", category="preferences", importance=0.8, write_markdown=False)
    store.remember("I prefer concise updates.", kind="semantic", category="preferences", importance=0.78, write_markdown=False)
    consolidator.consolidate(dry_run=False, similarity_threshold=0.85)

    with store._connection() as conn:
        archive_id = conn.execute("SELECT archive_id FROM memory_archive LIMIT 1").fetchone()["archive_id"]

    consolidator.restore(int(archive_id))

    assert len(active_contents(consolidator)) == 2
    assert consolidator.archive_count() == 0


def test_current_state_summary_is_generated(tmp_path):
    consolidator = make_consolidator(tmp_path)
    consolidator.store.remember(
        "Trinity runs local-first.",
        kind="decision",
        category="architecture",
        importance=0.95,
        write_markdown=False,
    )

    report = consolidator.consolidate(dry_run=False)

    assert report.summary_path is not None
    summary = (consolidator.store.vault / "runtime" / "current_state.md").read_text(encoding="utf-8")
    assert "Trinity runs local-first." in summary
    assert "decision / architecture" in summary


def test_exact_duplicate_across_categories_is_consolidated(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    text = "Remember permanently: My test project is called Phoenix and its primary language is Python."
    store.remember(text, kind="decision", category="conversation", importance=0.90, write_markdown=False)
    store.remember(text, kind="project", category="trinity-ai", importance=0.85, write_markdown=False)

    report = consolidator.consolidate(dry_run=False)

    assert report.duplicate_groups == 1
    assert report.archived_duplicates == 1
    assert active_contents(consolidator) == [text]


def test_conversation_prompt_noise_is_archived(tmp_path):
    consolidator = make_consolidator(tmp_path)
    store = consolidator.store
    store.remember(
        "Introduce yourself as Trinity in 3 short sentences.",
        kind="project",
        category="trinity-ai",
        importance=0.72,
        metadata={"source": "conversation"},
        write_markdown=False,
    )
    store.remember(
        "What is my test project called and what language does it use?",
        kind="project",
        category="trinity-ai",
        importance=0.72,
        metadata={"source": "conversation"},
        write_markdown=False,
    )

    report = consolidator.consolidate(dry_run=False)

    assert report.archived_prompt_noise == 2
    assert active_contents(consolidator) == []
    assert consolidator.archive_count() == 2
