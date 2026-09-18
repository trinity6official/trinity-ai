#!/usr/bin/env python3
"""Fail when Git tracks Trinity runtime state or generated local artifacts."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import PurePosixPath
from typing import Iterable

FORBIDDEN_EXACT = {
    ".env",
    "memory/trinity_brain.json",
    "trinity_brain.json",
}
FORBIDDEN_PREFIXES = (
    "backups/",
    "memory/daily_logs/",
    "memory/runtime/",
    "memory/vault/",
    "models/",
    "secrets/",
)
FORBIDDEN_DIR_NAMES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".gguf",
    ".key",
    ".log",
    ".pem",
    ".pid",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
    ".token",
)


def normalize(path: str) -> str:
    converted = path.replace("\\", "/")
    return "/".join(part for part in converted.split("/") if part not in ("", "."))


def forbidden_reason(path: str) -> str | None:
    """Return why a repository path must not be tracked, or ``None``."""
    normalized = normalize(path)
    if not normalized:
        return None
    if normalized in FORBIDDEN_EXACT or normalized.startswith(".env."):
        return "local runtime/config state"
    if normalized.startswith(FORBIDDEN_PREFIXES):
        return "runtime-generated directory"

    parts = PurePosixPath(normalized).parts
    if any(part in FORBIDDEN_DIR_NAMES for part in parts):
        return "generated cache directory"

    lowered = normalized.lower()
    if lowered.endswith(FORBIDDEN_SUFFIXES):
        return "generated, secret, model, or runtime artifact"
    return None


def find_forbidden_paths(paths: Iterable[str]) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for path in paths:
        reason = forbidden_reason(path)
        if reason:
            violations.append((normalize(path), reason))
    return sorted(set(violations))


def tracked_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that Git does not track Trinity runtime state or local artifacts."
    )
    parser.add_argument(
        "--git-index",
        action="store_true",
        help="Check paths currently tracked by Git.",
    )
    parser.add_argument("paths", nargs="*", help="Optional explicit paths to validate.")
    args = parser.parse_args()

    paths = tracked_paths() if args.git_index else args.paths
    if not paths:
        parser.error("provide --git-index or one or more paths")

    violations = find_forbidden_paths(paths)
    if not violations:
        print("Repository hygiene check passed: no runtime state is tracked.")
        return 0

    print("Repository hygiene check failed. Remove these paths from Git tracking:")
    for path, reason in violations:
        print(f"  - {path}: {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
