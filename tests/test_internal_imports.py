from pathlib import Path

from scripts.check_internal_imports import find_untracked_internal_imports


def test_internal_import_check_uses_git_tracking_not_working_tree_presence(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "trinity.py").write_text("from core.capabilities import CapabilityRegistry\n")
    # The module exists locally, but is deliberately absent from the simulated Git index.
    (core / "capabilities.py").write_text("class CapabilityRegistry: pass\n")

    tracked = {"core/trinity.py"}
    assert find_untracked_internal_imports(tmp_path, tracked) == [
        ("core/trinity.py", 1, "core.capabilities")
    ]


def test_internal_import_check_accepts_tracked_module(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "trinity.py").write_text("from core.capabilities import CapabilityRegistry\n")
    (core / "capabilities.py").write_text("class CapabilityRegistry: pass\n")

    tracked = {"core/trinity.py", "core/capabilities.py"}
    assert find_untracked_internal_imports(tmp_path, tracked) == []


def test_internal_import_check_catches_namespace_root_submodule_import(tmp_path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "trinity.py").write_text("from core import capabilities\n")
    (core / "capabilities.py").write_text("class CapabilityRegistry: pass\n")

    assert find_untracked_internal_imports(tmp_path, {"core/trinity.py"}) == [
        ("core/trinity.py", 1, "core.capabilities")
    ]
