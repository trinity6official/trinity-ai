"""Durable local memory store for Trinity.

SQLite is the operational source of truth for searchable memories. Markdown is
an intentionally human-readable vault for durable memories and daily history.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return value.lower() or "memory"


@dataclass(frozen=True)
class MemoryRecord:
    id: int
    kind: str
    category: str
    content: str
    importance: float
    created_at: str
    metadata: dict[str, Any]


class MemoryStore:
    """SQLite + Markdown storage with no cloud dependency."""

    def __init__(self, root: str | Path = "memory", db_path: str | Path | None = None):
        self.root = Path(root)
        self.db_path = Path(db_path) if db_path else self.root / "trinity_memory.db"
        self.vault = self.root / "vault"
        self._ensure_layout()
        self._init_db()

    def _ensure_layout(self) -> None:
        for directory in (
            self.root,
            self.vault / "identity",
            self.vault / "projects",
            self.vault / "knowledge",
            self.vault / "decisions",
            self.vault / "experiences",
            self.vault / "tasks",
            self.vault / "procedures",
            self.vault / "daily",
            self.vault / "runtime",
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        """Yield a transactional SQLite connection and always close it.

        ``sqlite3.Connection`` commits/rolls back when used as a context
        manager, but it does *not* close itself.  Trinity is designed to run
        continuously, so every short-lived operation must explicitly release
        its connection instead of relying on garbage collection.
        """
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
                CREATE TABLE IF NOT EXISTS migrations (
                    name TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )

    @staticmethod
    def fingerprint(kind: str, category: str, content: str) -> str:
        canonical = "|".join((kind.strip().lower(), category.strip().lower(), content.strip()))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def remember(
        self,
        content: str,
        *,
        kind: str = "semantic",
        category: str = "general",
        importance: float = 0.5,
        metadata: Optional[dict[str, Any]] = None,
        write_markdown: bool = True,
    ) -> int:
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty")
        importance = max(0.0, min(1.0, float(importance)))
        fingerprint = self.fingerprint(kind, category, content)
        now = _now()
        payload = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO memories
                   (fingerprint, kind, category, content, importance, created_at, updated_at, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(fingerprint) DO UPDATE SET
                     importance = MAX(memories.importance, excluded.importance),
                     updated_at = excluded.updated_at,
                     metadata_json = excluded.metadata_json""",
                (fingerprint, kind, category, content, importance, now, now, payload),
            )
            row = conn.execute("SELECT id FROM memories WHERE fingerprint = ?", (fingerprint,)).fetchone()
        if write_markdown and importance >= 0.7:
            self._append_markdown(kind, category, content, now, metadata or {})
        return int(row["id"])

    def _append_markdown(self, kind: str, category: str, content: str, timestamp: str, metadata: dict[str, Any]) -> None:
        directory = {
            "decision": "decisions",
            "episodic": "experiences",
            "procedural": "procedures",
            "task": "tasks",
            "identity": "identity",
            "project": "projects",
        }.get(kind, "knowledge")
        path = self.vault / directory / f"{_slug(category)}.md"
        fingerprint = self.fingerprint(kind, category, content)[:12]
        marker = f"<!-- memory:{fingerprint} -->"
        if path.exists() and marker in path.read_text(encoding="utf-8"):
            return
        if not path.exists():
            path.write_text(f"# {category.replace('_', ' ').title()}\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{marker}\n- {content}\n  - Recorded: {timestamp}\n")
            if metadata:
                handle.write(f"  - Metadata: `{json.dumps(metadata, ensure_ascii=False, sort_keys=True)}`\n")
            handle.write("\n")

    def add_daily_entry(self, content: str, timestamp: Optional[str] = None) -> Path:
        timestamp = timestamp or _now()
        day = timestamp[:10]
        path = self.vault / "daily" / f"{day}.md"
        if not path.exists():
            path.write_text(f"# Trinity Daily Memory — {day}\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"- **{timestamp}** — {content.strip()}\n")
        return path

    def search(self, query: str, *, limit: int = 10, kind: Optional[str] = None) -> list[MemoryRecord]:
        terms = [term.lower() for term in re.findall(r"[\w.-]+", query) if len(term) > 1]
        clauses, params = [], []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if terms:
            clauses.append("(" + " OR ".join("LOWER(content) LIKE ?" for _ in terms) + ")")
            params.extend(f"%{term}%" for term in terms)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"SELECT * FROM memories{where} ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._record(row) for row in rows]

    def recent(self, limit: int = 10) -> list[MemoryRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (max(1, int(limit)),)
            ).fetchall()
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"], kind=row["kind"], category=row["category"], content=row["content"],
            importance=row["importance"], created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def migration_completed(self, name: str) -> bool:
        with self._connection() as conn:
            return conn.execute("SELECT 1 FROM migrations WHERE name = ?", (name,)).fetchone() is not None

    def mark_migration(self, name: str, details: Optional[dict[str, Any]] = None) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO migrations(name, completed_at, details_json) VALUES (?, ?, ?)",
                (name, _now(), json.dumps(details or {}, sort_keys=True)),
            )

    def import_legacy_brain(self, brain: dict[str, Any], migration_name: str = "legacy_brain_v1") -> int:
        """Import durable legacy knowledge without deleting or rewriting the JSON source."""
        if self.migration_completed(migration_name):
            return 0
        count = 0
        durable_sections = {
            "identity": "identity",
            "david": "identity",
            "company": "project",
            "hardware": "semantic",
        }
        for section, kind in durable_sections.items():
            value = brain.get(section)
            if value:
                self.remember(json.dumps(value, ensure_ascii=False, sort_keys=True), kind=kind, category=section, importance=0.9)
                count += 1
        knowledge = brain.get("knowledge", {})
        for category, values in knowledge.items():
            if isinstance(values, list):
                for value in values:
                    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
                    self.remember(text, kind="semantic", category=category, importance=0.75)
                    count += 1
        for item in brain.get("history", {}).get("decisions_made", []):
            decision = item.get("decision") if isinstance(item, dict) else str(item)
            outcome = item.get("outcome") if isinstance(item, dict) else ""
            if decision:
                self.remember(f"{decision} — Outcome: {outcome}", kind="decision", category="legacy", importance=0.85, metadata=item if isinstance(item, dict) else {})
                count += 1
        self.mark_migration(migration_name, {"records_imported": count})
        return count
