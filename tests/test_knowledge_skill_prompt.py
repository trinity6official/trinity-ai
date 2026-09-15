from core.skill_manager import SkillManager


def test_personal_knowledge_query_includes_knowledge_skill_prompt():
    manager = SkillManager()
    prompt = manager.get_trinity_prompt(
        query="What did I write in my architecture notes?"
    )
    assert "KNOWLEDGE SKILL" in prompt
    assert "search_knowledge" in prompt


def test_general_greeting_does_not_force_knowledge_skill_prompt():
    manager = SkillManager()
    prompt = manager.get_trinity_prompt(query="hello")
    assert "KNOWLEDGE SKILL" not in prompt
