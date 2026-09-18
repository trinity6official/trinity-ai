from core.memory_pipeline import ConversationMemoryPipeline
from core.memory_store import MemoryStore

def test_session_history_searchable_but_not_durable(tmp_path):
    store=MemoryStore(root=tmp_path); p=ConversationMemoryPipeline(store, session_id="s1")
    p.persist("What did we discuss about Phoenix?", "We discussed Phoenix yesterday.")
    assert len(store.search_conversations("Phoenix")) == 1
    assert store.search("Phoenix") == []

def test_session_id_stable(tmp_path):
    store=MemoryStore(root=tmp_path); p=ConversationMemoryPipeline(store, session_id="stable")
    p.persist("First interaction", "First response"); p.persist("Second interaction", "Second response")
    assert {r.session_id for r in store.recent_conversations(limit=10)} == {"stable"}

def test_topic_search(tmp_path):
    store=MemoryStore(root=tmp_path)
    store.add_conversation_turn("We discussed buying an M6 Mac mini.", "The 32 GB model gives Trinity more headroom.", session_id="mac")
    assert len(store.search_conversations("What did we discuss about Mac Mini?")) == 1
    assert store.search_conversations("PostgreSQL") == []
