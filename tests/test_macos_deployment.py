import io
import plistlib
import sqlite3
import tarfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.macos_deployment import LaunchdConfig, MacInstaller, MacPreflight, MemoryBackupManager


def test_preflight_reports_required_local_tools():
    tools = {
        "ollama": "/opt/homebrew/bin/ollama",
        "osascript": "/usr/bin/osascript",
        "screencapture": "/usr/sbin/screencapture",
        "say": "/usr/bin/say",
        "ffmpeg": "/opt/homebrew/bin/ffmpeg",
    }
    report = MacPreflight(
        system=lambda: "Darwin",
        which=lambda name: tools.get(name),
        python_version=(3, 13, 0),
    ).run()
    assert report.ready is True
    assert {item.name for item in report.items} >= {"macOS", "Ollama", "AppleScript"}


def test_preflight_requires_ollama_but_screen_capture_is_optional():
    report = MacPreflight(
        system=lambda: "Darwin",
        which=lambda name: "/usr/bin/osascript" if name == "osascript" else None,
        python_version=(3, 12, 0),
    ).run()
    assert report.ready is False
    screen = next(item for item in report.items if item.name == "Screen capture")
    assert screen.required is False


def test_launchd_config_is_local_daemon_with_restart_policy(tmp_path):
    root = tmp_path / "trinity"; root.mkdir(); (root / "core").mkdir()
    payload = plistlib.loads(LaunchdConfig(root, "/usr/bin/python3").render())
    assert payload["Label"] == "com.trinity6.trinity-ai"
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] == {"SuccessfulExit": False}
    assert payload["WorkingDirectory"] == str(root.resolve())
    assert payload["ProgramArguments"][0].startswith("/usr/bin/python3")
    assert payload["ProgramArguments"][1:] == [
        "-m", "core.run", "--mode", "daemon"
    ]
    assert payload["EnvironmentVariables"]["TRINITY_DAEMON"] == "true"
    assert payload["EnvironmentVariables"]["TRINITY_TELEGRAM_NOTIFICATIONS"] == "false"


def test_installer_prepares_directories_and_user_launchagent(tmp_path):
    root = tmp_path / "project"; root.mkdir(); (root / "core").mkdir()
    home = tmp_path / "home"
    plist = MacInstaller(root, home=home, python_executable="/usr/bin/python3").prepare()
    assert plist.exists()
    assert plist.parent == home / "Library" / "LaunchAgents"
    assert (root / "logs").is_dir()
    assert (root / "backups").is_dir()
    assert (root / "memory" / "runtime").is_dir()


def test_memory_backup_contains_only_expected_memory(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    (root / "memory" / "vault").mkdir(parents=True)
    (root / "memory" / "vault" / "identity.md").write_text("Trinity")
    db_path = root / "memory" / "trinity_memory.db"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE memory_test(value TEXT)")
        conn.execute("INSERT INTO memory_test VALUES ('saved')")
    (root / ".env").write_text("TOKEN=secret")
    (root / "models").mkdir(); (root / "models" / "weights.bin").write_bytes(b"weights")

    backup = MemoryBackupManager(root).create(now=datetime(2026, 9, 15, tzinfo=timezone.utc))
    with tarfile.open(backup, "r:gz") as archive:
        names = archive.getnames()
    assert "memory/trinity_memory.db" in names
    assert any(name.startswith("memory/vault") for name in names)
    assert ".env" not in names
    assert not any(name.startswith("models") for name in names)


def test_memory_restore_requires_explicit_approval(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    (root / "memory").mkdir()
    db_path = root / "memory" / "trinity_memory.db"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE memory_test(value TEXT)")
        conn.execute("INSERT INTO memory_test VALUES ('saved')")
    backup = MemoryBackupManager(root).create(
        now=datetime(2026, 9, 15, tzinfo=timezone.utc)
    )
    with pytest.raises(PermissionError):
        MemoryBackupManager(root).restore(backup)


def test_memory_restore_rejects_path_traversal(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    archive_path = tmp_path / "bad.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        data = b"evil"
        info = tarfile.TarInfo("../evil.txt"); info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError):
        MemoryBackupManager(root).restore(archive_path, approved=True)


def test_memory_backup_restore_round_trip(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    (root / "memory" / "vault").mkdir(parents=True)
    db = root / "memory" / "trinity_memory.db"
    identity = root / "memory" / "vault" / "identity.md"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE memory_test(value TEXT)")
        conn.execute("INSERT INTO memory_test VALUES ('original-db')")
    identity.write_text("original identity")

    manager = MemoryBackupManager(root)
    backup = manager.create(now=datetime(2026, 9, 15, tzinfo=timezone.utc))
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DELETE FROM memory_test")
        conn.execute("INSERT INTO memory_test VALUES ('corrupted')")
    identity.write_text("changed")

    manager.restore(backup, approved=True)

    with closing(sqlite3.connect(db)) as conn, conn:
        assert conn.execute("SELECT value FROM memory_test").fetchone()[0] == "original-db"
    assert identity.read_text() == "original identity"


def test_memory_backup_captures_committed_wal_data(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    (root / "memory").mkdir()
    db = root / "memory" / "trinity_memory.db"

    writer = sqlite3.connect(db)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE memory_test(value TEXT)")
    writer.commit()
    writer.execute("INSERT INTO memory_test VALUES ('latest-committed-memory')")
    writer.commit()

    manager = MemoryBackupManager(root)
    backup = manager.create(now=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc))
    writer.close()

    extracted = tmp_path / "extracted"
    with tarfile.open(backup, "r:gz") as archive:
        archive.extractall(extracted, filter="data")
    snapshot = extracted / "memory" / "trinity_memory.db"
    with closing(sqlite3.connect(snapshot)) as conn:
        values = [row[0] for row in conn.execute("SELECT value FROM memory_test")]
    assert values == ["latest-committed-memory"]
