from types import SimpleNamespace
from core.conversation import ConversationService
from core.memory_store import MemoryStore

def test_history_recall_explicit_only(tmp_path):
    store=MemoryStore(root=tmp_path); service=ConversationService(SimpleNamespace(memory_store=store))
    store.add_conversation_turn("We discussed the M6 Mac mini.", "It will run Trinity.", session_id="mac")
    assert "M6 Mac mini" in service._retrieve_session_context("What did we discuss about Mac Mini?")
    assert service._retrieve_session_context("What is a Mac Mini?") == ""

def test_history_windows():
    assert ConversationService._history_window_days("What did we discuss last week?") == 14
    assert ConversationService._history_window_days("Do you remember last month?") == 62
