from core.skill_manager import SkillManager


def test_prompt_advertises_session_tools():
    prompt = SkillManager().get_trinity_prompt(query="search my recent conversation sessions")
    assert "search_sessions" in prompt
    assert "get_recent_sessions" in prompt
