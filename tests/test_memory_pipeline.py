from core.memory_pipeline import ConversationMemoryPipeline
from core.memory_store import MemoryStore


def make_pipeline(tmp_path):
    return ConversationMemoryPipeline(MemoryStore(root=tmp_path / "memory"))


def test_decision_is_persisted(tmp_path):
    pipeline = make_pipeline(tmp_path)
    ids = pipeline.persist("We'll go with local AI permanently for Trinity.", "Understood.")
    assert ids
    results = pipeline.store.search("local AI")
    assert any(r.kind == "decision" for r in results)


def test_preference_is_persisted(tmp_path):
    pipeline = make_pipeline(tmp_path)
    pipeline.persist("I prefer concise status updates.", "Got it.")
    results = pipeline.store.search("concise")
    assert any(r.category == "preferences" for r in results)


def test_transient_ack_is_not_durable_memory(tmp_path):
    pipeline = make_pipeline(tmp_path)
    assert pipeline.persist("Okay", "Ready.") == []
    assert pipeline.store.search("Okay") == []


def test_duplicate_memory_is_deduplicated(tmp_path):
    pipeline = make_pipeline(tmp_path)
    text = "I prefer local models for Trinity."
    pipeline.persist(text, "Noted.")
    pipeline.persist(text, "Noted again.")
    matches = [r for r in pipeline.store.search("local models", limit=20) if r.content == text]
    assert len(matches) <= 2  # preference + project categories, never duplicate rows within either
    assert len({(r.kind, r.category, r.content) for r in matches}) == len(matches)


def test_recall_context(tmp_path):
    pipeline = make_pipeline(tmp_path)
    pipeline.persist("Trinity architecture will use local AI permanently.", "Saved.")
    context = pipeline.recall_context("Trinity local AI")
    assert "local AI" in context
