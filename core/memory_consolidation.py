"""Deterministic, reversible memory consolidation for Trinity.

V1 deliberately avoids an LLM deciding what to delete. It groups conservative
near-duplicates, moves superseded/low-value records into an archive table,
promotes the surviving canonical memory, and writes a compact current-state
summary. Archived records are preserved in SQLite and can be restored.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from core.memory_store import MemoryRecord, MemoryStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ConsolidationReport:
    scanned: int
    duplicate_groups: int
    archived_duplicates: int
    archived_low_value: int
    archived_prompt_noise: int
    promoted: int
    archive_total: int
    summary_path: str | None
    dry_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryConsolidator:
    """Consolidate Trinity memories without permanently deleting source data."""

    PROTECTED_KINDS = {"identity", "project", "decision", "procedural", "task"}
    PROTECTED_CATEGORIES = {"explicit", "preferences"}
    NEGATIONS = {"no", "not", "never", "dont", "don't", "without", "cannot", "can't"}
    REQUEST_PREFIXES = (
        "what ", "when ", "where ", "who ", "why ", "how ",
        "can ", "could ", "would ", "will you ", "do ", "does ", "did ",
        "tell me ", "show me ", "give me ", "help me ", "introduce ",
        "explain ", "check ", "find ", "create ", "make ", "write ",
        "run ", "open ", "close ", "list ", "summarize ", "compare ",
    )

    def __init__(self, store: MemoryStore):
        self.store = store
        self._ensure_archive_table()

    def _ensure_archive_table(self) -> None:
        with self.store._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_archive (
                    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    archived_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    superseded_by INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_memory_archive_original
                    ON memory_archive(original_id);
                CREATE INDEX IF NOT EXISTS idx_memory_archive_reason
                    ON memory_archive(reason);
                """
            )

    def _active_records(self) -> list[MemoryRecord]:
        with self.store._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC, id ASC"
            ).fetchall()
        return [self.store._record(row) for row in rows]

    @staticmethod
    def _normalize(text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip().lower()
        value = re.sub(
            r"^(?:please\s+)?(?:remember(?:\s+permanently)?(?:\s+(?:that|this))?|"
            r"do\s+not\s+forget(?:\s+(?:that|this))?|don't\s+forget(?:\s+(?:that|this))?)"
            r"\s*[:,-]?\s*",
            "",
            value,
        )
        value = re.sub(r"[^a-z0-9._'-]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9._'-]+", cls._normalize(text)))

    @classmethod
    def _conflict_signals(cls, left: str, right: str) -> bool:
        left_tokens, right_tokens = cls._tokens(left), cls._tokens(right)
        if bool(left_tokens & cls.NEGATIONS) != bool(right_tokens & cls.NEGATIONS):
            return True
        left_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", cls._normalize(left))
        right_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", cls._normalize(right))
        return bool(left_numbers and right_numbers and left_numbers != right_numbers)

    @classmethod
    def similarity(cls, left: str, right: str) -> float:
        if cls._conflict_signals(left, right):
            return 0.0
        a, b = cls._normalize(left), cls._normalize(right)
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        seq = SequenceMatcher(None, a, b).ratio()
        ta, tb = cls._tokens(a), cls._tokens(b)
        jaccard = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
        return max(seq, jaccard)

    def _duplicate_groups(
        self,
        records: Iterable[MemoryRecord],
        threshold: float,
    ) -> list[list[MemoryRecord]]:
        records = list(records)
        if len(records) < 2:
            return []

        parent = {record.id: record.id for record in records}

        def find(value: int) -> int:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(left: int, right: int) -> None:
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        # Exact normalized duplicates are safe to merge even when an older
        # extractor classified the same fact into different kinds/categories.
        exact: dict[str, list[MemoryRecord]] = defaultdict(list)
        for record in records:
            normalized = self._normalize(record.content)
            if normalized:
                exact[normalized].append(record)
        for group in exact.values():
            for record in group[1:]:
                union(group[0].id, record.id)

        # Fuzzy near-duplicate matching stays conservative: only compare
        # records already classified into the same kind/category.
        buckets: dict[tuple[str, str], list[MemoryRecord]] = defaultdict(list)
        for record in records:
            buckets[(record.kind, record.category)].append(record)
        for bucket in buckets.values():
            for index, left in enumerate(bucket):
                for right in bucket[index + 1 :]:
                    if self.similarity(left.content, right.content) >= threshold:
                        union(left.id, right.id)

        clustered: dict[int, list[MemoryRecord]] = defaultdict(list)
        for record in records:
            clustered[find(record.id)].append(record)
        return [group for group in clustered.values() if len(group) > 1]

    @staticmethod
    def _canonical(group: list[MemoryRecord]) -> MemoryRecord:
        return max(
            group,
            key=lambda record: (
                record.importance,
                len(record.content),
                record.created_at,
                -record.id,
            ),
        )

    def _archive(self, memory_id: int, *, reason: str, superseded_by: int | None = None) -> bool:
        with self.store._connection() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                return False
            conn.execute(
                """INSERT INTO memory_archive
                   (original_id, fingerprint, kind, category, content, importance,
                    created_at, updated_at, metadata_json, archived_at, reason, superseded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"], row["fingerprint"], row["kind"], row["category"],
                    row["content"], row["importance"], row["created_at"], row["updated_at"],
                    row["metadata_json"], _now(), reason, superseded_by,
                ),
            )
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return True

    def _promote_canonical(self, canonical: MemoryRecord, archived_ids: list[int]) -> bool:
        if not archived_ids:
            return False
        new_importance = min(0.99, canonical.importance + min(0.10, 0.02 * len(archived_ids)))
        with self.store._connection() as conn:
            row = conn.execute(
                "SELECT metadata_json, importance FROM memories WHERE id = ?", (canonical.id,)
            ).fetchone()
            if row is None:
                return False
            metadata = json.loads(row["metadata_json"] or "{}")
            existing = {int(value) for value in metadata.get("consolidated_from", []) if str(value).isdigit()}
            metadata["consolidated_from"] = sorted(existing | set(archived_ids))
            metadata["consolidated_at"] = _now()
            metadata["consolidation_count"] = len(metadata["consolidated_from"])
            conn.execute(
                """UPDATE memories
                   SET importance = ?, updated_at = ?, metadata_json = ?
                   WHERE id = ?""",
                (
                    max(float(row["importance"]), new_importance),
                    _now(),
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    canonical.id,
                ),
            )
        return True

    @staticmethod
    def _age_days(record: MemoryRecord, now: datetime) -> int:
        try:
            value = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return max(0, (now - value.astimezone(timezone.utc)).days)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _eligible_prompt_noise(cls, record: MemoryRecord) -> bool:
        metadata = record.metadata or {}
        if metadata.get("source") != "conversation":
            return False
        if record.category == "explicit":
            return False
        lower = re.sub(r"\s+", " ", record.content.strip().lower())
        return lower.endswith("?") or lower.startswith(cls.REQUEST_PREFIXES)

    def _eligible_low_value(self, record: MemoryRecord, *, threshold: float, age_days: int) -> bool:
        if record.kind in self.PROTECTED_KINDS or record.category in self.PROTECTED_CATEGORIES:
            return False
        if record.importance > threshold:
            return False
        return self._age_days(record, datetime.now(timezone.utc)) >= age_days

    def archive_count(self) -> int:
        with self.store._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM memory_archive").fetchone()
        return int(row["total"])

    def restore(self, archive_id: int) -> int:
        """Restore one archived memory to the active store and remove its archive copy."""
        with self.store._connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_archive WHERE archive_id = ?", (archive_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Archived memory not found: {archive_id}")
        memory_id = self.store.remember(
            row["content"],
            kind=row["kind"],
            category=row["category"],
            importance=float(row["importance"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            write_markdown=False,
        )
        with self.store._connection() as conn:
            conn.execute("DELETE FROM memory_archive WHERE archive_id = ?", (archive_id,))
        return memory_id

    def _write_current_state(self, minimum_importance: float = 0.7, limit: int = 50) -> Path:
        records = [r for r in self._active_records() if r.importance >= minimum_importance]
        records.sort(key=lambda r: (-r.importance, r.kind, r.category, r.created_at))
        records = records[: max(1, int(limit))]
        path = self.store.vault / "runtime" / "current_state.md"
        lines = [
            "# Trinity Current Memory State",
            "",
            f"Generated: {_now()}",
            "",
            "This file is generated from active durable memories. Archived source records remain in SQLite.",
            "",
        ]
        grouped: dict[tuple[str, str], list[MemoryRecord]] = defaultdict(list)
        for record in records:
            grouped[(record.kind, record.category)].append(record)
        for (kind, category), items in sorted(grouped.items()):
            lines.extend([f"## {kind} / {category}", ""])
            for record in items:
                lines.append(f"- {record.content}  _(importance {record.importance:.2f})_")
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path

    def consolidate(
        self,
        *,
        dry_run: bool = True,
        similarity_threshold: float = 0.85,
        low_value_threshold: float = 0.25,
        low_value_age_days: int = 30,
    ) -> ConsolidationReport:
        threshold = max(0.0, min(1.0, float(similarity_threshold)))
        active = self._active_records()
        groups = self._duplicate_groups(active, threshold)

        duplicate_ids: set[int] = set()
        archived_duplicates = 0
        promoted = 0
        for group in groups:
            canonical = self._canonical(group)
            duplicates = [record for record in group if record.id != canonical.id]
            duplicate_ids.update(record.id for record in duplicates)
            archived_duplicates += len(duplicates)
            if duplicates:
                promoted += 1
            if not dry_run:
                archived_ids: list[int] = []
                for duplicate in duplicates:
                    if self._archive(
                        duplicate.id,
                        reason="near_duplicate",
                        superseded_by=canonical.id,
                    ):
                        archived_ids.append(duplicate.id)
                self._promote_canonical(canonical, archived_ids)

        archived_prompt_noise = 0
        prompt_noise_ids: set[int] = set()
        for record in active:
            if record.id in duplicate_ids:
                continue
            if self._eligible_prompt_noise(record):
                prompt_noise_ids.add(record.id)
                archived_prompt_noise += 1
                if not dry_run:
                    self._archive(record.id, reason="conversation_prompt_noise")

        archived_low_value = 0
        for record in active:
            if record.id in duplicate_ids or record.id in prompt_noise_ids:
                continue
            if self._eligible_low_value(
                record,
                threshold=low_value_threshold,
                age_days=max(0, int(low_value_age_days)),
            ):
                archived_low_value += 1
                if not dry_run:
                    self._archive(record.id, reason="low_value_aged")

        summary_path = None
        if not dry_run:
            summary_path = str(self._write_current_state())

        return ConsolidationReport(
            scanned=len(active),
            duplicate_groups=len(groups),
            archived_duplicates=archived_duplicates,
            archived_low_value=archived_low_value,
            archived_prompt_noise=archived_prompt_noise,
            promoted=promoted,
            archive_total=self.archive_count(),
            summary_path=summary_path,
            dry_run=dry_run,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate Trinity's local durable memory")
    parser.add_argument("--root", default="memory", help="Memory root directory")
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run")
    parser.add_argument("--similarity", type=float, default=0.85, help="Near-duplicate threshold")
    parser.add_argument("--low-value-threshold", type=float, default=0.25)
    parser.add_argument("--low-value-age-days", type=int, default=30)
    parser.add_argument("--restore", type=int, default=None, metavar="ARCHIVE_ID")
    args = parser.parse_args()

    consolidator = MemoryConsolidator(MemoryStore(root=Path(args.root)))
    if args.restore is not None:
        restored_id = consolidator.restore(args.restore)
        print(json.dumps({"restored_memory_id": restored_id}, indent=2))
        return 0

    report = consolidator.consolidate(
        dry_run=not args.apply,
        similarity_threshold=args.similarity,
        low_value_threshold=args.low_value_threshold,
        low_value_age_days=args.low_value_age_days,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
