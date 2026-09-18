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


def test_retired_skill_builder_direct_write_path_cannot_return():
    """PR #6 leaves generated skill writes behind one governed proposal service."""
    assert not (ROOT / "skills" / "skill_builder_skill.py").exists()
    active_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in _python_files()
    ).lower()
    assert "_auto_build_new_skill" not in active_text
    assert "_auto_implement_missing_tool" not in active_text


def test_conversation_routes_capability_gaps_to_skill_evolution_service():
    source = (ROOT / "core" / "conversation_tasks.py").read_text(encoding="utf-8")
    assert "evolution.propose_new_skill(" in source
    assert "evolution.propose_missing_tool(" in source

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


def test_agent_registry_exposes_explicit_execution_request_boundary():
    """PR #6 gives agents the same immutable request boundary as skills."""
    source = (ROOT / "core" / "agent_runtime.py").read_text(encoding="utf-8")
    assert "def execute_request(self, request: AgentExecutionRequest)" in source
    assert "AgentExecutionRequest(" in source


def test_trinity_owns_one_capability_registry_for_discovery_and_exposure():
    """PR #7 centralizes discovery metadata without moving execution ownership."""
    trinity = (ROOT / "core" / "trinity.py").read_text(encoding="utf-8")
    assert "self.capabilities = CapabilityRegistry(" in trinity
    assert "self.skills.bind_capability_registry(self.capabilities)" in trinity


def test_interface_surfaces_consume_capability_registry_when_bound():
    api_bridge = (ROOT / "core" / "api_bridge.py").read_text(encoding="utf-8")
    conversation = (ROOT / "core" / "conversation.py").read_text(encoding="utf-8")
    status = (ROOT / "core" / "status_service.py").read_text(encoding="utf-8")
    assert 'registry.interface_manifest("api")' in api_bridge
    assert 'registry.skill_names(interface="conversation")' in conversation
    assert 'registry.skill_names(interface="conversation")' in status


def test_ci_guards_against_untracked_internal_imports_and_imports_composition_root():
    workflow = (ROOT / ".github" / "workflows" / "trinity.yml").read_text(encoding="utf-8")
    assert "python scripts/check_internal_imports.py --git-index" in workflow
    assert 'python -c "import core.trinity"' in workflow
    assert 'python -m pytest -q -m "not network"' in workflow


def test_self_evolution_approval_surfaces_exact_review_material():
    source = (ROOT / "core" / "skill_evolution.py").read_text(encoding="utf-8")
    assert '"review": proposal.review' in source
    assert "Review this exact diff before approval" in source
    assert "self.host.skills.execute_request(" in source


def test_retired_consciousness_skill_file_cannot_return():
    assert not (ROOT / "skills" / "consciousness_skill.py").exists()
