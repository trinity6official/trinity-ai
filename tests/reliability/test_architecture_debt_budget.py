from __future__ import annotations

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_ROOTS = ("core", "voice", "agents", "skills")


def _python_files():
    for root_name in ACTIVE_ROOTS:
        root = ROOT / root_name
        yield from root.rglob("*.py")


def _relative_paths_containing(token: str) -> set[str]:
    needle = token.lower()
    return {
        path.relative_to(ROOT).as_posix()
        for path in _python_files()
        if needle in path.read_text(encoding="utf-8", errors="ignore").lower()
    }


def _imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == module_name or alias.name.startswith(module_name + ".") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == module_name or module.startswith(module_name + "."):
                return True
    return False


def test_known_telegram_coupling_cannot_spread_before_removal():
    """Freeze the current Telegram debt so PR #3 can only reduce it.

    This is intentionally a debt budget, not an endorsement of the listed files.
    New production modules may not acquire Telegram knowledge while the feature is
    being removed.
    """
    allowed = {
        "agents/content_agent.py",
        "agents/github_agent.py",
        "core/android_test.py",
        "core/api_bridge.py",
        "core/attachments.py",
        "core/bootstrap.py",
        "core/briefing.py",
        "core/channels/__init__.py",
        "core/channels/telegram.py",
        "core/commands.py",
        "core/conversation.py",
        "core/decisions.py",
        "core/doctor.py",
        "core/lifecycle.py",
        "core/macos_deployment.py",
        "core/message_service.py",
        "core/notifications.py",
        "core/proactive_service.py",
        "core/run.py",
        "core/run_with_api.py",
        "core/skill_evolution.py",
        "core/status_service.py",
        "core/trinity.py",
        "voice/speak.py",
    }
    current = _relative_paths_containing("telegram")
    assert current <= allowed, f"Telegram coupling spread into: {sorted(current - allowed)}"


def test_legacy_brain_file_coupling_cannot_spread_before_memory_consolidation():
    """Legacy JSON brain ownership is known debt and may only shrink."""
    allowed = {
        "core/consciousness.py",
        "core/macos_deployment.py",
        "core/memory.py",
        "core/skill_manager.py",
        "core/trinity.py",
        "skills/memory_skill.py",
    }
    current = _relative_paths_containing("trinity_brain.json")
    assert current <= allowed, f"Legacy brain coupling spread into: {sorted(current - allowed)}"


def test_self_modifying_skill_generation_cannot_spread_before_retirement():
    """Keep executable self-generation contained until it is replaced by procedures."""
    allowed = {
        "core/conversation.py",
        "core/proactive.py",
        "core/response_processing.py",
        "core/skill_evolution.py",
        "core/skill_manager.py",
        "core/trinity.py",
        "skills/skill_builder_skill.py",
    }
    tokens = ("trinity_skill_need", "skillevolutionservice", "skill_builder")
    current: set[str] = set()
    for token in tokens:
        current |= _relative_paths_containing(token)
    assert current <= allowed, f"Self-modifying skill generation spread into: {sorted(current - allowed)}"


def test_application_source_never_imports_test_code():
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files()
        if _imports_module(path, "tests")
    ]
    assert offenders == []


def test_trinity_composition_root_is_imported_only_by_runtime_entrypoints():
    """Prevent ordinary services/skills from reaching back into the god object."""
    allowed = {"core/daemon.py", "core/run.py"}
    offenders = {
        path.relative_to(ROOT).as_posix()
        for path in _python_files()
        if path.relative_to(ROOT).as_posix() != "core/trinity.py"
        and _imports_module(path, "core.trinity")
    }
    assert offenders <= allowed, f"New imports of core.trinity: {sorted(offenders - allowed)}"
