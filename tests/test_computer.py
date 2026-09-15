import json
import sys
from pathlib import Path

from core.audit import ActionAuditTrail
from core.computer import ComputerController


class FakeDesktop:
    name = "fake"

    def __init__(self):
        self.calls = []

    def available(self):
        return True

    def frontmost_app(self):
        self.calls.append(("frontmost_app",))
        return "Terminal"

    def running_apps(self):
        self.calls.append(("running_apps",))
        return ["Finder", "Terminal"]

    def capture_screen(self):
        self.calls.append(("capture_screen",))
        return b"\x89PNGfake"

    def open_app(self, app_name):
        self.calls.append(("open_app", app_name))
        return f"Opened {app_name}"

    def activate_app(self, app_name):
        self.calls.append(("activate_app", app_name))
        return f"Activated {app_name}"

    def type_text(self, text):
        self.calls.append(("type_text", text))
        return "Typed text"

    def click(self, x, y):
        self.calls.append(("click", x, y))
        return f"Clicked {x},{y}"


def test_list_directory_is_workspace_scoped(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    controller = ComputerController([tmp_path])
    result = controller.list_directory(".")
    assert result.success is True
    assert "a.txt" in result.output


def test_read_text_inside_workspace(tmp_path):
    (tmp_path / "note.txt").write_text("hello")
    result = ComputerController([tmp_path]).read_text("note.txt")
    assert result.success is True
    assert result.output == "hello"


def test_path_escape_is_blocked(tmp_path):
    result = ComputerController([tmp_path]).read_text("../outside.txt")
    assert result.success is False
    assert "outside Trinity workspace" in result.error


def test_command_requires_approval(tmp_path):
    controller = ComputerController([tmp_path])
    result = controller.run_command([sys.executable, "-c", "print('ok')"])
    assert result.success is False
    assert result.requires_approval is True
    assert result.permission == "high_risk"


def test_approved_command_runs_without_shell(tmp_path):
    controller = ComputerController([tmp_path])
    result = controller.run_command(
        [sys.executable, "-c", "print('ok')"],
        approved=True,
    )
    assert result.success is True
    assert result.output.strip() == "ok"


def test_frontmost_app_is_safe_observation(tmp_path):
    provider = FakeDesktop()
    result = ComputerController([tmp_path], provider=provider).frontmost_app()
    assert result.success is True
    assert result.output == "Terminal"
    assert result.permission == "safe"


def test_running_apps_is_safe_observation(tmp_path):
    result = ComputerController([tmp_path], provider=FakeDesktop()).running_apps()
    assert result.success is True
    assert result.output.splitlines() == ["Finder", "Terminal"]


def test_capture_screen_is_local_safe_observation(tmp_path):
    capture = ComputerController([tmp_path], provider=FakeDesktop()).capture_screen()
    assert capture.success is True
    assert capture.image == b"\x89PNGfake"
    assert capture.permission == "safe"


def test_desktop_mutation_requires_approval(tmp_path):
    provider = FakeDesktop()
    controller = ComputerController([tmp_path], provider=provider)
    result = controller.open_app("Safari")
    assert result.success is False
    assert result.requires_approval is True
    assert provider.calls == []


def test_approved_desktop_mutations_reach_provider(tmp_path):
    provider = FakeDesktop()
    controller = ComputerController([tmp_path], provider=provider)
    assert controller.open_app("Safari", approved=True).success
    assert controller.activate_app("Terminal", approved=True).success
    assert controller.type_text("hello", approved=True).success
    assert controller.click(10, 20, approved=True).success
    assert provider.calls == [
        ("open_app", "Safari"),
        ("activate_app", "Terminal"),
        ("type_text", "hello"),
        ("click", 10, 20),
    ]


def test_computer_actions_are_audited(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit = ActionAuditTrail(audit_path)
    provider = FakeDesktop()
    controller = ComputerController([tmp_path], provider=provider, audit_trail=audit)

    controller.frontmost_app()
    controller.type_text("secret-ish content")
    controller.type_text("approved", approved=True)

    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    statuses = [(entry["action"], entry["status"]) for entry in entries]
    assert ("computer.frontmost_app", "completed") in statuses
    assert ("computer.type_text", "approval_required") in statuses
    assert ("computer.type_text", "approved") in statuses
    assert ("computer.type_text", "completed") in statuses
