"""Permission-aware local computer skill for Trinity."""
from __future__ import annotations

from dataclasses import asdict


class ComputerSkill:
    name = "computer"
    description = "Observe and control the local Mac through Trinity's permission-gated desktop controller"

    def __init__(self, computer_controller=None):
        self.computer = computer_controller

    def get_tools(self):
        return [
            {"name": "frontmost_app", "description": "Get the active local application", "params": [], "needs_approval": False},
            {"name": "list_running_apps", "description": "List visible running applications", "params": [], "needs_approval": False},
            {"name": "list_directory", "description": "List a directory inside Trinity's configured workspace", "params": ["path"], "needs_approval": False},
            {"name": "read_text", "description": "Read a text file inside Trinity's configured workspace", "params": ["path"], "needs_approval": False},
            {"name": "open_app", "description": "Open a macOS application", "params": ["app_name"], "needs_approval": True},
            {"name": "activate_app", "description": "Bring an application to the foreground", "params": ["app_name"], "needs_approval": True},
            {"name": "type_text", "description": "Type text into the active application", "params": ["text"], "needs_approval": True},
            {"name": "click", "description": "Click screen coordinates", "params": ["x", "y"], "needs_approval": True},
            {"name": "run_command", "description": "Run an argv-based local command inside Trinity's workspace", "params": ["argv", "cwd"], "needs_approval": True},
        ]

    @staticmethod
    def _result(value):
        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)
        return value

    def execute(self, tool_name, params, approved=False):
        if self.computer is None:
            return {"success": False, "error": "Local computer controller is unavailable"}
        params = dict(params or {})
        try:
            if tool_name == "frontmost_app":
                return self._result(self.computer.frontmost_app())
            if tool_name == "list_running_apps":
                return self._result(self.computer.running_apps())
            if tool_name == "list_directory":
                return self._result(self.computer.list_directory(params.get("path", ".")))
            if tool_name == "read_text":
                return self._result(self.computer.read_text(params["path"]))
            if tool_name == "open_app":
                return self._result(self.computer.open_app(params["app_name"], approved=approved))
            if tool_name == "activate_app":
                return self._result(self.computer.activate_app(params["app_name"], approved=approved))
            if tool_name == "type_text":
                return self._result(self.computer.type_text(params["text"], approved=approved))
            if tool_name == "click":
                return self._result(self.computer.click(int(params["x"]), int(params["y"]), approved=approved))
            if tool_name == "run_command":
                argv = params.get("argv", [])
                if isinstance(argv, str):
                    return {"success": False, "error": "run_command requires argv as a list, not a shell string"}
                return self._result(self.computer.run_command(
                    argv,
                    cwd=params.get("cwd", "."),
                    approved=approved,
                ))
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except (KeyError, TypeError, ValueError) as exc:
            return {"success": False, "error": f"Invalid parameters for {tool_name}: {exc}"}
