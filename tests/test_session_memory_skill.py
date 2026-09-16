from core.memory_store import MemoryStore
from skills.memory_skill import MemorySkill

def test_session_tools(tmp_path):
    store=MemoryStore(root=tmp_path)
    store.add_conversation_turn("PostgreSQL onboarding completed.", "Supported.", session_id="db")
    skill=MemorySkill(brain_file=str(tmp_path / "trinity_brain.json"))
    result=skill.search_sessions("PostgreSQL", days=30, limit=5)
    assert result["total_matches"] == 1 and result["matches"][0]["session_id"] == "db"
    assert {"search_sessions", "get_recent_sessions"} <= {t["name"] for t in skill.get_tools()}
