"""Permission-aware local computer observation and control for Trinity.

The controller exposes a provider-neutral surface. Read-only/local observations may
run autonomously, while anything that changes the desktop is approval-gated and
audited. No action uses a shell string; commands are always passed as argv.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from core.audit import ActionAuditTrail
from core.permissions import PermissionEngine, PermissionLevel


@dataclass(frozen=True)
class ComputerResult:
    success: bool
    output: str = ""
    error: str | None = None
    requires_approval: bool = False
    action_id: str | None = None
    permission: str | None = None


@dataclass(frozen=True)
class ScreenCapture:
    success: bool
    image: bytes | None = None
    media_type: str = "image/png"
    error: str | None = None
    requires_approval: bool = False
    action_id: str | None = None
    permission: str | None = None


class DesktopProvider(Protocol):
    """Platform adapter used by :class:`ComputerController`."""

    name: str

    def available(self) -> bool: ...
    def frontmost_app(self) -> str: ...
    def running_apps(self) -> Sequence[str]: ...
    def capture_screen(self) -> bytes: ...
    def open_app(self, app_name: str) -> str: ...
    def activate_app(self, app_name: str) -> str: ...
    def type_text(self, text: str) -> str: ...
    def click(self, x: int, y: int) -> str: ...


class MacOSDesktopProvider:
    """Narrow macOS desktop adapter using built-in system commands only.

    Accessibility and Screen Recording permissions are deliberately left to macOS
    to enforce. Trinity never attempts to bypass those OS protections.
    """

    name = "macos"

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def available(self) -> bool:
        return (
            platform.system() == "Darwin"
            and shutil.which("osascript") is not None
            and shutil.which("open") is not None
        )

    def _run(self, argv: Sequence[str]) -> str:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            shell=False,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "command failed").strip()
            raise RuntimeError(detail)
        return (completed.stdout or "").strip()

    def _osascript(self, script: str, *args: str) -> str:
        return self._run(["osascript", "-e", script, *args])

    def frontmost_app(self) -> str:
        return self._osascript(
            'tell application "System Events" to get name of first application process whose frontmost is true'
        )

    def running_apps(self) -> Sequence[str]:
        output = self._osascript(
            'tell application "System Events" to get name of every application process whose background only is false'
        )
        return [item.strip() for item in output.split(",") if item.strip()]

    def capture_screen(self) -> bytes:
        screencapture = shutil.which("screencapture")
        if not screencapture:
            raise RuntimeError("macOS screencapture utility is unavailable")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
                tmp_path = handle.name
            self._run([screencapture, "-x", "-t", "png", tmp_path])
            return Path(tmp_path).read_bytes()
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    def open_app(self, app_name: str) -> str:
        if not app_name.strip():
            raise ValueError("App name cannot be empty")
        self._run(["open", "-a", app_name])
        return f"Opened {app_name}"

    def activate_app(self, app_name: str) -> str:
        if not app_name.strip():
            raise ValueError("App name cannot be empty")
        script = """
on run argv
  set appName to item 1 of argv
  tell application appName to activate
end run
""".strip()
        self._osascript(script, app_name)
        return f"Activated {app_name}"

    def type_text(self, text: str) -> str:
        script = """
on run argv
  tell application "System Events" to keystroke (item 1 of argv)
end run
""".strip()
        self._osascript(script, text)
        return "Typed text"

    def click(self, x: int, y: int) -> str:
        script = """
on run argv
  set xPos to (item 1 of argv) as integer
  set yPos to (item 2 of argv) as integer
  tell application "System Events" to click at {xPos, yPos}
end run
""".strip()
        self._osascript(script, str(int(x)), str(int(y)))
        return f"Clicked {int(x)},{int(y)}"


def default_desktop_provider() -> DesktopProvider | None:
    provider = MacOSDesktopProvider()
    return provider if provider.available() else None


class ComputerController:
    """Workspace-scoped filesystem plus approval-gated desktop/process control."""

    def __init__(
        self,
        workspace_roots: Sequence[str | Path] | None = None,
        permissions: PermissionEngine | None = None,
        audit_trail: ActionAuditTrail | None = None,
        provider: DesktopProvider | None = None,
    ) -> None:
        roots = workspace_roots or [os.environ.get("TRINITY_WORKSPACE", os.getcwd())]
        self.workspace_roots = tuple(Path(root).expanduser().resolve() for root in roots)
        self.permissions = permissions or PermissionEngine()
        self.audit = audit_trail
        self.provider = provider if provider is not None else default_desktop_provider()

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.workspace_roots[0] / candidate
        resolved = candidate.resolve()
        if not any(resolved == root or root in resolved.parents for root in self.workspace_roots):
            raise PermissionError(f"Path is outside Trinity workspace: {resolved}")
        return resolved

    def _record(self, action: str, status: str, *, action_id: str | None = None, **kwargs) -> str | None:
        if self.audit is None:
            return action_id
        return self.audit.record(
            actor_type="computer",
            action=f"computer.{action}",
            status=status,
            action_id=action_id,
            **kwargs,
        )

    def _authorize(self, action: str, params: dict, approved: bool) -> tuple[object, str | None, ComputerResult | None]:
        decision = self.permissions.assess_tool("computer", action)
        action_id = self._record(
            action,
            "requested",
            permission=decision.level.value,
            approved=approved,
            params=params,
        )
        if decision.level == PermissionLevel.FORBIDDEN:
            self._record(action, "denied", action_id=action_id, permission=decision.level.value, error=decision.reason)
            return decision, action_id, ComputerResult(False, error=decision.reason, action_id=action_id, permission=decision.level.value)
        if decision.requires_confirmation and not approved:
            self._record(action, "approval_required", action_id=action_id, permission=decision.level.value, error=decision.reason)
            return decision, action_id, ComputerResult(
                False,
                error=decision.reason,
                requires_approval=True,
                action_id=action_id,
                permission=decision.level.value,
            )
        if decision.requires_confirmation:
            self._record(action, "approved", action_id=action_id, permission=decision.level.value, approved=True)
        self._record(action, "started", action_id=action_id, permission=decision.level.value, approved=approved)
        return decision, action_id, None

    def _complete(self, action: str, action_id: str | None, permission: str, output: str = "") -> ComputerResult:
        self._record(action, "completed", action_id=action_id, permission=permission, result={"output": output})
        return ComputerResult(True, output=output, action_id=action_id, permission=permission)

    def _fail(self, action: str, action_id: str | None, permission: str, exc: Exception | str) -> ComputerResult:
        error = str(exc)
        self._record(action, "failed", action_id=action_id, permission=permission, error=error)
        return ComputerResult(False, error=error, action_id=action_id, permission=permission)

    def _provider_or_error(self) -> DesktopProvider:
        if self.provider is None or not self.provider.available():
            raise RuntimeError("No supported local desktop provider is available")
        return self.provider

    def list_directory(self, path: str | Path = ".") -> ComputerResult:
        action = "list_directory"
        decision, action_id, blocked = self._authorize(action, {"path": str(path)}, True)
        if blocked:
            return blocked
        try:
            resolved = self._resolve(path)
            if not resolved.is_dir():
                raise NotADirectoryError(f"Not a directory: {resolved}")
            items = "\n".join(sorted(item.name for item in resolved.iterdir()))
            return self._complete(action, action_id, decision.level.value, items)
        except Exception as exc:
            return self._fail(action, action_id, decision.level.value, exc)

    def read_text(self, path: str | Path, max_chars: int = 100_000) -> ComputerResult:
        action = "read_text"
        decision, action_id, blocked = self._authorize(action, {"path": str(path)}, True)
        if blocked:
            return blocked
        try:
            resolved = self._resolve(path)
            if not resolved.is_file():
                raise FileNotFoundError(f"Not a file: {resolved}")
            text = resolved.read_text(encoding="utf-8")
            return self._complete(action, action_id, decision.level.value, text[:max_chars])
        except Exception as exc:
            return self._fail(action, action_id, decision.level.value, exc)

    def frontmost_app(self) -> ComputerResult:
        action = "frontmost_app"
        decision, action_id, blocked = self._authorize(action, {}, True)
        if blocked:
            return blocked
        try:
            output = self._provider_or_error().frontmost_app()
            return self._complete(action, action_id, decision.level.value, output)
        except Exception as exc:
            return self._fail(action, action_id, decision.level.value, exc)

    def running_apps(self) -> ComputerResult:
        action = "list_running_apps"
        decision, action_id, blocked = self._authorize(action, {}, True)
        if blocked:
            return blocked
        try:
            output = "\n".join(self._provider_or_error().running_apps())
            return self._complete(action, action_id, decision.level.value, output)
        except Exception as exc:
            return self._fail(action, action_id, decision.level.value, exc)

    def capture_screen(self) -> ScreenCapture:
        action = "capture_screen"
        decision, action_id, blocked = self._authorize(action, {}, True)
        if blocked:
            return ScreenCapture(
                False,
                error=blocked.error,
                requires_approval=blocked.requires_approval,
                action_id=blocked.action_id,
                permission=blocked.permission,
            )
        try:
            image = self._provider_or_error().capture_screen()
            self._record(
                action,
                "completed",
                action_id=action_id,
                permission=decision.level.value,
                result={"bytes": len(image), "media_type": "image/png"},
            )
            return ScreenCapture(True, image=image, action_id=action_id, permission=decision.level.value)
        except Exception as exc:
            self._record(action, "failed", action_id=action_id, permission=decision.level.value, error=str(exc))
            return ScreenCapture(False, error=str(exc), action_id=action_id, permission=decision.level.value)

    def _desktop_action(self, action: str, params: dict, fn, *, approved: bool) -> ComputerResult:
        decision, action_id, blocked = self._authorize(action, params, approved)
        if blocked:
            return blocked
        try:
            output = fn(self._provider_or_error())
            return self._complete(action, action_id, decision.level.value, output)
        except Exception as exc:
            return self._fail(action, action_id, decision.level.value, exc)

    def open_app(self, app_name: str, *, approved: bool = False) -> ComputerResult:
        return self._desktop_action(
            "open_app", {"app_name": app_name}, lambda provider: provider.open_app(app_name), approved=approved
        )

    def activate_app(self, app_name: str, *, approved: bool = False) -> ComputerResult:
        return self._desktop_action(
            "activate_app", {"app_name": app_name}, lambda provider: provider.activate_app(app_name), approved=approved
        )

    def type_text(self, text: str, *, approved: bool = False) -> ComputerResult:
        return self._desktop_action(
            "type_text", {"text": text}, lambda provider: provider.type_text(text), approved=approved
        )

    def click(self, x: int, y: int, *, approved: bool = False) -> ComputerResult:
        return self._desktop_action(
            "click", {"x": int(x), "y": int(y)}, lambda provider: provider.click(int(x), int(y)), approved=approved
        )

    def run_command(
        self,
        argv: Sequence[str],
        *,
        approved: bool = False,
        cwd: str | Path = ".",
        timeout: int = 30,
    ) -> ComputerResult:
        action = "run_command"
        decision, action_id, blocked = self._authorize(
            action,
            {"argv": list(argv), "cwd": str(cwd)},
            approved,
        )
        if blocked:
            return blocked
        if not argv:
            return self._fail(action, action_id, decision.level.value, "Command cannot be empty")
        try:
            resolved_cwd = self._resolve(cwd)
            completed = subprocess.run(
                list(argv),
                cwd=resolved_cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            if completed.returncode != 0:
                raise RuntimeError(f"Exit code {completed.returncode}: {output.strip()}")
            return self._complete(action, action_id, decision.level.value, output)
        except Exception as exc:
            return self._fail(action, action_id, decision.level.value, exc)
