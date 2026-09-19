from unittest.mock import MagicMock

from core.skill_manager import SkillManager
from core.permissions import PermissionEngine


def test_safe_read_tool_executes():
    sm = SkillManager()
    skill = MagicMock()
    skill.execute.return_value = {"success": True}
    sm._skill_cache["github"] = skill
    result = sm.execute("github", "read_file", {"repo": "x", "path": "y"})
    assert result["success"] is True
    skill.execute.assert_called_once()


def test_external_send_defaults_to_confirmation():
    sm = SkillManager()
    skill = MagicMock()
    skill.get_tools.return_value = [{"name": "send_email", "needs_approval": False}]
    sm._skill_cache["email"] = skill
    result = sm.execute("email", "send_email", {"to": "x"})
    assert result["success"] is False
    assert result["needs_approval"] is True
    skill.execute.assert_not_called()


def test_external_send_executes_only_after_pending_approval():
    sm = SkillManager()
    skill = MagicMock()
    skill.get_tools.return_value = [{"name": "send_email", "needs_approval": False}]
    skill.execute.return_value = {"success": True}
    sm._skill_cache["email"] = skill

    pending = sm.execute("email", "send_email", {"to": "x"})
    result = sm.approve_action(pending["approval_id"])

    assert result["success"] is True
    skill.execute.assert_called_once_with("send_email", {"to": "x"})


def test_legacy_approved_keyword_cannot_bypass_pending_approval():
    sm = SkillManager()
    skill = MagicMock()
    skill.execute.return_value = {"success": True}
    sm._skill_cache["email"] = skill

    result = sm.execute("email", "send_email", {"to": "x"}, approved=True)

    assert result["success"] is False
    assert result["permission_denied"] is True
    skill.execute.assert_not_called()


def test_staged_github_mutation_can_prepare_change():
    sm = SkillManager()
    skill = MagicMock()
    skill.get_tools.return_value = [{"name": "update_file", "needs_approval": True}]
    skill.execute.return_value = {"success": True, "needs_approval": True}
    sm._skill_cache["github"] = skill
    result = sm.execute("github", "update_file", {"repo": "x"})
    assert result["needs_approval"] is True
    skill.execute.assert_called_once()


def test_high_risk_command_is_gated():
    sm = SkillManager()
    skill = MagicMock()
    sm._skill_cache["system"] = skill
    result = sm.execute("system", "run_command", {"cmd": "rm -rf /"})
    assert result["success"] is False
    assert result["permission"] == "high_risk"
    skill.execute.assert_not_called()


def test_local_memory_mutation_remains_available():
    sm = SkillManager()
    skill = MagicMock()
    skill.execute.return_value = {"success": True}
    sm._skill_cache["memory"] = skill
    result = sm.execute("memory", "update_david", {"key": "x", "value": "y"})
    assert result["success"] is True


def test_self_improvement_github_commit_requires_explicit_approval(monkeypatch):
    manager = SkillManager(permission_engine=PermissionEngine())
    skill = MagicMock()
    skill.get_tools.return_value = [{"name": "self_commit_improvement", "needs_approval": True}]
    manager._skill_cache["github"] = skill
    blocked = manager.execute("github", "self_commit_improvement", {"path": "skills/x.py"})
    assert blocked["needs_approval"] is True
    skill.execute.assert_not_called()


def test_unverified_source_cannot_read_tools_autonomously():
    from core.trust_context import RequestSource, TrustContext, use_trust_context

    sm = SkillManager()
    skill = MagicMock()
    skill.execute.return_value = {"success": True}
    sm._skill_cache["github"] = skill

    with use_trust_context(TrustContext.unverified(source=RequestSource.LOCAL_VOICE)):
        result = sm.execute("github", "read_file", {"repo": "x", "path": "y"})

    assert result["success"] is False
    assert result["needs_approval"] is True
    skill.execute.assert_not_called()


def test_verified_remote_source_retains_normal_safe_access():
    from core.trust_context import TrustContext, use_trust_context

    sm = SkillManager()
    skill = MagicMock()
    skill.execute.return_value = {"success": True}
    sm._skill_cache["github"] = skill

    with use_trust_context(TrustContext.verified_remote(subject="david", device_id="phone")):
        result = sm.execute("github", "read_file", {"repo": "x", "path": "y"})

    assert result["success"] is True
    skill.execute.assert_called_once()
