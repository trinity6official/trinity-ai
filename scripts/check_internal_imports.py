#!/usr/bin/env python3
"""Verify that internal Python imports resolve to files tracked by Git.

This catches a subtle failure mode where a developer has an untracked module in
an otherwise healthy working tree: local tests can import it, while a clean CI
checkout cannot.  The check deliberately reasons from the Git index rather than
from files present on disk.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
from typing import Iterable

INTERNAL_ROOTS = {"core", "voice", "skills", "agents", "scripts"}


def tracked_paths() -> set[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        item.decode("utf-8").replace("\\", "/")
        for item in completed.stdout.split(b"\0")
        if item
    }


def _module_candidates(module: str) -> tuple[str, str]:
    base = module.replace(".", "/")
    return f"{base}.py", f"{base}/__init__.py"


def _module_tracked(module: str, tracked: set[str]) -> bool:
    if not module:
        return True
    root = module.split(".", 1)[0]
    if root not in INTERNAL_ROOTS:
        return True
    if module == root:
        prefix = root + "/"
        return any(path.startswith(prefix) for path in tracked)
    return any(candidate in tracked for candidate in _module_candidates(module))


def _package_for_source(source: str) -> list[str]:
    parts = Path(source).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    else:
        parts = parts[:-1]
    return list(parts)


def _resolve_relative(source: str, node: ast.ImportFrom) -> str:
    package = _package_for_source(source)
    # level=1 means current package, level=2 means parent, etc.
    remove = max(node.level - 1, 0)
    if remove:
        package = package[:-remove] if remove <= len(package) else []
    suffix = node.module.split(".") if node.module else []
    return ".".join([*package, *suffix])


def find_untracked_internal_imports(
    root: str | Path,
    tracked: Iterable[str],
) -> list[tuple[str, int, str]]:
    repo_root = Path(root)
    tracked_set = {str(path).replace("\\", "/") for path in tracked}
    violations: list[tuple[str, int, str]] = []

    for source in sorted(tracked_set):
        if not source.endswith(".py"):
            continue
        top = source.split("/", 1)[0]
        if top not in INTERNAL_ROOTS:
            continue
        path = repo_root / source
        if not path.exists():
            # A tracked path missing from the working tree is a separate Git error.
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=source)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = (
                    _resolve_relative(source, node)
                    if node.level
                    else (node.module or "")
                )
                modules.append(base)
                # ``from core import api`` imports a submodule even though the
                # namespace package itself has no core/__init__.py.
                if base in INTERNAL_ROOTS:
                    for alias in node.names:
                        if alias.name != "*":
                            # Namespace-root imports such as ``from core import api``
                            # must resolve to a tracked submodule. Do not consult the
                            # working tree here: an untracked local file is exactly
                            # the failure mode this check is designed to catch.
                            modules.append(f"{base}.{alias.name}")

            for module in modules:
                if not _module_tracked(module, tracked_set):
                    violations.append((source, int(getattr(node, "lineno", 0)), module))

    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that internal imports resolve to Git-tracked modules."
    )
    parser.add_argument(
        "--git-index",
        action="store_true",
        help="Use the current Git index as the authoritative source set.",
    )
    args = parser.parse_args()
    if not args.git_index:
        parser.error("--git-index is required")

    tracked = tracked_paths()
    violations = find_untracked_internal_imports(Path.cwd(), tracked)
    if not violations:
        print("Internal import check passed: all internal modules are tracked by Git.")
        return 0

    print("Internal import check failed. These tracked sources import untracked modules:")
    for source, line, module in violations:
        print(f"  - {source}:{line} -> {module}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
