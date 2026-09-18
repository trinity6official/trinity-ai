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


def test_removed_remote_chat_coupling_cannot_return():
    """PR #3 retires the old remote-chat transport from active application code."""
    assert _relative_paths_containing("telegram") == set()


def test_legacy_brain_files_are_confined_to_migration_and_backup_boundaries():
    """PR #4 makes legacy JSON a migration input, never an active memory owner."""
    allowed = {
        "core/consciousness.py",
        "core/macos_deployment.py",
        "core/memory.py",
    }
    current = _relative_paths_containing("trinity_brain.json")
    assert current <= allowed, f"Legacy brain coupling escaped migration boundaries: {sorted(current - allowed)}"


def test_memory_store_construction_is_confined_to_memory_owners_and_test_harnesses():
    """Runtime skills/services must receive the shared store instead of creating one."""
    allowed = {
        "core/android_test.py",
        "core/memory.py",
        "core/memory_consolidation.py",
    }
    current = _relative_paths_containing("memorystore(")
    assert current <= allowed, f"MemoryStore ownership spread into: {sorted(current - allowed)}"


def test_self_modifying_skill_generation_cannot_spread_before_retirement():
    """Track active self-modification calls, not harmless prompt/status strings."""
    allowed_callers = {
        "core/conversation_tasks.py",
        "core/trinity.py",
    }
    active_calls = set()
    guarded_methods = {"_auto_build_new_skill", "_auto_implement_missing_tool"}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in guarded_methods
            for node in ast.walk(tree)
        ):
            active_calls.add(path.relative_to(ROOT).as_posix())
    assert active_calls <= allowed_callers, (
        f"Self-modifying execution spread into: {sorted(active_calls - allowed_callers)}"
    )


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


def test_conversation_reasoning_does_not_execute_skill_calls_directly():
    """PR #5 keeps task execution outside prompt/context assembly."""
    conversation = (ROOT / "core" / "conversation.py").read_text(encoding="utf-8")
    assert "process_skill_call(" not in conversation
    assert "ConversationTaskService" in conversation


def test_skill_manager_exposes_explicit_execution_request_boundary():
    """All governed skill execution must have a typed request entry point."""
    source = (ROOT / "core" / "skill_manager.py").read_text(encoding="utf-8")
    assert "def execute_request(self, request: ExecutionRequest)" in source
    assert "ExecutionRequest(" in source
