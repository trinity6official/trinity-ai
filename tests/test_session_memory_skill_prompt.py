from pathlib import Path

def test_prompt_advertises_session_tools():
    text=Path("core/skill_manager.py").read_text(encoding="utf-8")
    assert "search_sessions(query, days, limit)" in text
    assert "get_recent_sessions(days, limit)" in text
