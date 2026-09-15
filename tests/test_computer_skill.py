from types import SimpleNamespace
from unittest.mock import MagicMock

from core.computer import ComputerResult
from core.permissions import PermissionEngine
from core.skill_manager import SkillManager
from skills.computer_skill import ComputerSkill


class FakeComputer:
    def frontmost_app(self):
        return ComputerResult(True, output="Terminal", permission="safe")
    def running_apps(self):
        return ComputerResult(True, output="Finder\nTerminal", permission="safe")
    def list_directory(self, path="."):
        return ComputerResult(True, output="README.md", permission="safe")
    def read_text(self, path):
        return ComputerResult(True, output="hello", permission="safe")
    def open_app(self, app_name, approved=False):
        return ComputerResult(approved, output=f"Opened {app_name}" if approved else "", requires_approval=not approved)
    def activate_app(self, app_name, approved=False):
        return ComputerResult(approved, output=f"Activated {app_name}" if approved else "", requires_approval=not approved)
    def type_text(self, text, approved=False):
        return ComputerResult(approved, output="Typed text" if approved else "", requires_approval=not approved)
    def click(self, x, y, approved=False):
        return ComputerResult(approved, output=f"Clicked {x},{y}" if approved else "", requires_approval=not approved)
    def run_command(self, argv, cwd=".", approved=False):
        return ComputerResult(approved, output="ok" if approved else "", requires_approval=not approved)


def test_computer_skill_exposes_safe_observation():
    skill = ComputerSkill(FakeComputer())
    result = skill.execute("frontmost_app", {})
    assert result["success"] is True
    assert result["output"] == "Terminal"


def test_computer_skill_mutation_receives_approved_context():
    skill = ComputerSkill(FakeComputer())
    assert skill.execute("open_app", {"app_name": "Safari"})["success"] is False
    assert skill.execute("open_app", {"app_name": "Safari"}, approved=True)["success"] is True


def test_skill_manager_queues_then_resumes_computer_action():
    manager = SkillManager(
        permission_engine=PermissionEngine(),
        computer_controller=FakeComputer(),
    )
    manager._skill_cache["computer"] = ComputerSkill(FakeComputer())
    blocked = manager.execute("computer", "open_app", {"app_name": "Safari"})
    assert blocked["needs_approval"] is True
    approval_id = blocked["approval_id"]
    assert approval_id in manager.get_pending_actions()
    result = manager.approve_action(approval_id)
    assert result["success"] is True
    assert result["output"] == "Opened Safari"
    assert manager.get_pending_actions() == {}


def test_shell_string_is_rejected_even_after_approval():
    skill = ComputerSkill(FakeComputer())
    result = skill.execute("run_command", {"argv": "rm -rf /"}, approved=True)
    assert result["success"] is False
    assert "argv as a list" in result["error"]
