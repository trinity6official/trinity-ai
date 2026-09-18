from types import SimpleNamespace
from unittest.mock import MagicMock

from core.skill_evolution import SkillEvolutionService


def test_invalid_new_skill_name_is_rejected(tmp_path):
    host = SimpleNamespace(llm=object())
    result = SkillEvolutionService(host, tmp_path).build_new_skill("bad/name", "x")
    assert result[0] is False


def test_missing_existing_skill_is_not_created_by_tool_extension(tmp_path):
    host = SimpleNamespace()
    assert SkillEvolutionService(host, tmp_path).implement_missing_tool("missing", "read_x", {}, object()) is False


def test_missing_tool_is_drafted_but_not_written_until_approval(tmp_path):
    skill = tmp_path / "demo_skill.py"
    original = "class DemoSkill:\n    name='demo'\n"
    skill.write_text(original)
    generated = (
        "class DemoSkill:\n"
        "    name='demo'\n"
        "    def read_x(self): return {'success': True}\n"
    )
    skills = MagicMock(); skills.execute.return_value = {"success": True}; skills.get_skill.return_value = object()
    host = SimpleNamespace(skills=skills, audit=None, respond=MagicMock(), consciousness=MagicMock())
    host._invoke_with_failover = lambda *a, **k: SimpleNamespace(content=generated)
    service = SkillEvolutionService(host, tmp_path)

    # Compatibility return remains False so the failed tool is NOT silently retried.
    assert service.implement_missing_tool("demo", "read_x", {}, object()) is False
    assert skill.read_text() == original
    proposal_id = next(iter(service.get_pending_changes()))
    assert skills.execute.call_count == 0

    success, _ = service.approve(proposal_id)
    assert success is True
    assert "def read_x" in skill.read_text()
    skills.reload_skill.assert_called_once_with("demo")
    assert skills.execute.call_args.args[0:2] == ("github", "self_commit_improvement")
    assert skills.execute.call_args.kwargs["approved"] is True


def test_new_skill_is_only_created_after_approval(tmp_path):
    (tmp_path / "web_skill.py").write_text("class WebSkill:\n    name='web'\n")
    generated = '''class EmailSkill:\n    name = "email"\n    def get_tools(self): return []\n    def execute(self, tool_name, params): return {"success": True}\n    def a(self): return {"success": True}\n    def b(self): return {"success": True}\n    def c(self): return {"success": True}\n'''
    skills = MagicMock(); skills.get_skill.return_value = object(); skills.execute.return_value = {"success": True}
    host = SimpleNamespace(llm=object(), skills=skills, audit=None, respond=MagicMock(), consciousness=MagicMock())
    host._invoke_with_failover = lambda *a, **k: SimpleNamespace(content=generated)
    service = SkillEvolutionService(host, tmp_path)
    ok, message = service.build_new_skill("email", "Inbox triage")
    assert ok is False and "approval required" in message
    assert not (tmp_path / "email_skill.py").exists()
    proposal_id = next(iter(service.get_pending_changes()))
    assert service.approve(proposal_id)[0] is True
    assert (tmp_path / "email_skill.py").exists()


def test_cancel_discards_proposal_without_writing(tmp_path):
    skill = tmp_path / "demo_skill.py"; skill.write_text("class DemoSkill:\n    name='demo'\n")
    generated = "class DemoSkill:\n    name='demo'\n    def read_x(self): return {'success': True}\n"
    host = SimpleNamespace(skills=MagicMock(), audit=None, respond=MagicMock())
    host._invoke_with_failover = lambda *a, **k: SimpleNamespace(content=generated)
    service = SkillEvolutionService(host, tmp_path)
    service.implement_missing_tool("demo", "read_x", {}, object())
    proposal_id = next(iter(service.get_pending_changes()))
    assert service.cancel(proposal_id) is True
    assert service.get_pending_changes() == {}
    assert "read_x" not in skill.read_text()
