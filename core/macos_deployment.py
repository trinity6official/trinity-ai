"""macOS installation, preflight and local Memory Vault backup helpers."""
from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from core.permissions import PermissionEngine, PermissionLevel


LAUNCHD_LABEL = "com.trinity6.trinity-ai"


@dataclass(frozen=True)
class PreflightItem:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class PreflightReport:
    items: tuple[PreflightItem, ...]

    @property
    def ready(self) -> bool:
        return all(item.ok for item in self.items if item.required)


class MacPreflight:
    """Check local prerequisites without changing the machine."""

    def __init__(
        self,
        *,
        system: Callable[[], str] = platform.system,
        which: Callable[[str], str | None] = shutil.which,
        python_version: Sequence[int] | None = None,
    ) -> None:
        self.system = system
        self.which = which
        self.python_version = tuple(python_version or sys.version_info[:3])

    def run(self) -> PreflightReport:
        system_name = self.system()
        items = [
            PreflightItem("macOS", system_name == "Darwin", f"platform={system_name}"),
            PreflightItem(
                "Python 3.11+",
                self.python_version >= (3, 11),
                ".".join(map(str, self.python_version)),
            ),
            PreflightItem("Ollama", self.which("ollama") is not None, self.which("ollama") or "not found"),
            PreflightItem("AppleScript", self.which("osascript") is not None, self.which("osascript") or "not found"),
            PreflightItem(
                "macOS speech",
                self.which("say") is not None,
                self.which("say") or "not found",
                required=False,
            ),
            PreflightItem(
                "Microphone capture",
                self.which("ffmpeg") is not None,
                self.which("ffmpeg") or "not found",
                required=False,
            ),
            PreflightItem(
                "Screen capture",
                self.which("screencapture") is not None,
                self.which("screencapture") or "not found",
                required=False,
            ),
        ]
        return PreflightReport(tuple(items))


class LaunchdConfig:
    """Render a user LaunchAgent for Trinity's local daemon."""

    def __init__(self, project_root: str | Path, python_executable: str | Path | None = None) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.python_executable = Path(python_executable or sys.executable).expanduser().resolve()

    def payload(self) -> dict:
        log_dir = self.project_root / "logs"
        return {
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": [
                str(self.python_executable),
                "-m",
                "core.run",
                "--mode",
                "daemon",
            ],
            "WorkingDirectory": str(self.project_root),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 10,
            "ProcessType": "Interactive",
            "StandardOutPath": str(log_dir / "trinity.out.log"),
            "StandardErrorPath": str(log_dir / "trinity.err.log"),
            "EnvironmentVariables": {
                "PYTHONUNBUFFERED": "1",
                "TRINITY_DAEMON": "true",
                "TRINITY_PRESENCE_ENABLED": "true",
                "TRINITY_API_ENABLED": "true",
            },
        }

    def render(self) -> bytes:
        return plistlib.dumps(self.payload(), fmt=plistlib.FMT_XML, sort_keys=True)

    def write(self, path: str | Path) -> Path:
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.render())
        return path


class MemoryBackupManager:
    """Create/restore local backups without including caches, model weights or secrets."""

    INCLUDE = (
        "memory/trinity_brain.json",
        "memory/trinity_memory.db",
        "memory/vault",
        "memory/runtime",
        "trinity_brain.json",
    )

    def __init__(
        self,
        project_root: str | Path,
        backup_dir: str | Path | None = None,
        *,
        permissions: PermissionEngine | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.backup_dir = Path(backup_dir or self.project_root / "backups").expanduser().resolve()
        self.permissions = permissions or PermissionEngine()

    def _add_sqlite_snapshot(self, archive: tarfile.TarFile, source: Path, arcname: str) -> None:
        """Archive a transactionally consistent SQLite snapshot, including WAL commits."""
        with tempfile.TemporaryDirectory(prefix="trinity-memory-backup-") as temp_dir:
            snapshot = Path(temp_dir) / source.name
            try:
                with closing(sqlite3.connect(str(source))) as source_db, closing(sqlite3.connect(str(snapshot))) as snapshot_db:
                    source_db.backup(snapshot_db)
            except sqlite3.DatabaseError as exc:
                raise RuntimeError(f"Cannot create a consistent Memory Vault backup: {exc}") from exc
            archive.add(snapshot, arcname=arcname, recursive=False)

    def create(self, *, now: datetime | None = None) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
        target = self.backup_dir / f"trinity-memory-{stamp}.tar.gz"
        with tarfile.open(target, "w:gz") as archive:
            for relative in self.INCLUDE:
                source = self.project_root / relative
                if not source.exists():
                    continue
                if relative == "memory/trinity_memory.db":
                    self._add_sqlite_snapshot(archive, source, relative)
                else:
                    archive.add(source, arcname=relative, recursive=True)
        return target

    @staticmethod
    def _safe_members(archive: tarfile.TarFile, destination: Path):
        destination = destination.resolve()
        for member in archive.getmembers():
            resolved = (destination / member.name).resolve()
            if resolved != destination and destination not in resolved.parents:
                raise ValueError(f"Unsafe backup member: {member.name}")
            if member.issym() or member.islnk():
                raise ValueError(f"Links are not allowed in Trinity backups: {member.name}")
            yield member

    def restore(self, archive_path: str | Path, *, approved: bool = False) -> None:
        decision = self.permissions.assess_action("restore_memory")
        if decision.level == PermissionLevel.FORBIDDEN:
            raise PermissionError(decision.reason)
        if decision.requires_confirmation and not approved:
            raise PermissionError("Memory restore requires explicit approval")

        archive_path = Path(archive_path).expanduser().resolve()
        with tarfile.open(archive_path, "r:gz") as archive:
            members = list(self._safe_members(archive, self.project_root))
            archive.extractall(self.project_root, members=members, filter="data")


class MacInstaller:
    """Prepare local runtime directories and LaunchAgent file; never auto-load it."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        home: str | Path | None = None,
        python_executable: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.home = Path(home or Path.home()).expanduser().resolve()
        self.launchd = LaunchdConfig(self.project_root, python_executable)

    @property
    def plist_path(self) -> Path:
        return self.home / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"

    def prepare(self) -> Path:
        for relative in ("logs", "backups", "memory/runtime", "memory/vault"):
            (self.project_root / relative).mkdir(parents=True, exist_ok=True)
        return self.launchd.write(self.plist_path)


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trinity macOS local deployment helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    sub.add_parser("install")
    backup = sub.add_parser("backup")
    backup.add_argument("--output-dir", default=None)
    restore = sub.add_parser("restore")
    restore.add_argument("archive")
    restore.add_argument(
        "--approve",
        action="store_true",
        help="Explicitly approve replacing Trinity memory from this backup",
    )
    args = parser.parse_args(argv)

    root = _default_root()
    if args.command == "preflight":
        report = MacPreflight().run()
        for item in report.items:
            marker = "OK" if item.ok else ("WARN" if not item.required else "MISSING")
            print(f"[{marker}] {item.name}: {item.detail}")
        return 0 if report.ready else 1
    if args.command == "install":
        report = MacPreflight().run()
        if not report.ready:
            print("Preflight failed. Run: python -m core.macos_deployment preflight")
            return 1
        plist = MacInstaller(root).prepare()
        print(f"Prepared LaunchAgent: {plist}")
        print("The service was not loaded automatically. Review the plist before enabling it.")
        return 0
    if args.command == "backup":
        path = MemoryBackupManager(root, args.output_dir).create()
        print(path)
        return 0
    if args.command == "restore":
        try:
            MemoryBackupManager(root).restore(args.archive, approved=args.approve)
        except PermissionError as exc:
            print(f"Restore blocked: {exc}")
            print("Review the backup, then repeat with --approve if you intend to restore it.")
            return 2
        print("Memory backup restored.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
