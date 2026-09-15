"""Local personal-knowledge index for Trinity.

This store is separate from conversational memory and web search. It indexes
only user-approved local roots, keeps source/line references, and refreshes
incrementally without any cloud dependency or embedding model.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_TOKEN_RE = re.compile(r"[\w.-]+", re.UNICODE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with",
}

SUPPORTED_SUFFIXES = {
    ".txt", ".md", ".rst", ".py", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".csv", ".tsv", ".sh", ".ps1", ".rb", ".go", ".js", ".ts",
    ".tsx", ".jsx", ".html", ".htm", ".css", ".sql", ".xml", ".java", ".c",
    ".h", ".cpp", ".hpp", ".rs", ".swift", ".kt", ".kts",
}
SUPPORTED_NAMES = {
    "readme", "license", "makefile", "dockerfile", "gemfile", "rakefile",
    "procfile",
}
IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv", "env",
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "models", "memory",
}


@dataclass(frozen=True)
class KnowledgeHit:
    source_path: str
    title: str
    chunk_index: int
    start_line: int
    end_line: int
    score: float
    content: str

    @property
    def source_ref(self) -> str:
        return f"{self.source_path}#L{self.start_line}-L{self.end_line}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_ref": self.source_ref,
            "title": self.title,
            "chunk_index": self.chunk_index,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": round(self.score, 4),
            "content": self.content,
        }


class KnowledgeIndex:
    """Incremental lexical index for approved local text/code documents."""

    def __init__(
        self,
        db_path: str | Path = "memory/knowledge_index.db",
        *,
        chunk_chars: int = 1600,
        overlap_lines: int = 2,
        max_file_bytes: int = 2_000_000,
        max_files_per_scan: int = 5000,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.chunk_chars = max(400, int(chunk_chars))
        self.overlap_lines = max(0, int(overlap_lines))
        self.max_file_bytes = max(1024, int(max_file_bytes))
        self.max_files_per_scan = max(1, int(max_files_per_scan))
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _connection(self):
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

                CREATE TABLE IF NOT EXISTS roots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    recursive INTEGER NOT NULL DEFAULT 1,
                    is_directory INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    UNIQUE(document_id, chunk_index)
                );

                CREATE TABLE IF NOT EXISTS terms (
                    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
                    term TEXT NOT NULL,
                    frequency INTEGER NOT NULL,
                    PRIMARY KEY(chunk_id, term)
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_terms_term ON terms(term);
                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_knowledge_documents_path ON documents(path);
                """
            )

    @staticmethod
    def _normalize(path: str | Path) -> Path:
        return Path(path).expanduser().resolve()

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [
            token.lower()
            for token in _TOKEN_RE.findall(text)
            if len(token) > 1 and token.lower() not in _STOP_WORDS
        ]

    @staticmethod
    def _supported(path: Path) -> bool:
        return (
            path.suffix.lower() in SUPPORTED_SUFFIXES
            or path.name.lower() in SUPPORTED_NAMES
        )

    @staticmethod
    def _hidden_or_ignored(path: Path, root: Path) -> bool:
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
        for part in relative.parts[:-1]:
            if part.startswith(".") or part.lower() in IGNORED_DIRECTORIES:
                return True
        return False

    def _iter_files(self, root: Path, recursive: bool) -> Iterator[Path]:
        if root.is_file():
            yield root
            return
        iterator = root.rglob("*") if recursive else root.glob("*")
        count = 0
        for path in iterator:
            if count >= self.max_files_per_scan:
                break
            if not path.is_file():
                continue
            if self._hidden_or_ignored(path, root):
                continue
            if not self._supported(path):
                continue
            count += 1
            yield path

    def _read_text(self, path: Path) -> tuple[str | None, str | None]:
        try:
            size = path.stat().st_size
        except OSError as exc:
            return None, str(exc)
        if size > self.max_file_bytes:
            return None, f"file exceeds {self.max_file_bytes} bytes"
        try:
            raw = path.read_bytes()
        except OSError as exc:
            return None, str(exc)
        if b"\x00" in raw[:8192]:
            return None, "binary file"
        try:
            return raw.decode("utf-8-sig"), None
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace"), None

    def _chunks(self, text: str) -> list[tuple[int, int, str]]:
        lines = text.splitlines()
        if not lines:
            return []
        chunks: list[tuple[int, int, str]] = []
        start = 0
        total = len(lines)
        while start < total:
            end = start
            chars = 0
            while end < total:
                next_size = len(lines[end]) + 1
                if end > start and chars + next_size > self.chunk_chars:
                    break
                chars += next_size
                end += 1
            if end == start:
                end += 1
            content = "\n".join(lines[start:end]).strip()
            if content:
                chunks.append((start + 1, end, content))
            if end >= total:
                break
            next_start = end - self.overlap_lines
            if next_start <= start:
                next_start = start + 1
            start = next_start
        return chunks

    def _remember_root(self, root: Path, recursive: bool) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO roots(path, recursive, is_directory, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    recursive=excluded.recursive,
                    is_directory=excluded.is_directory
                """,
                (str(root), int(bool(recursive)), int(root.is_dir()), _now()),
            )

    def _index_file(self, path: Path) -> dict[str, Any]:
        try:
            stat = path.stat()
        except OSError as exc:
            return {"path": str(path), "status": "error", "reason": str(exc)}

        if not self._supported(path):
            return {"path": str(path), "status": "skipped", "reason": "unsupported file type"}
        if stat.st_size > self.max_file_bytes:
            return {
                "path": str(path),
                "status": "skipped",
                "reason": f"file exceeds {self.max_file_bytes} bytes",
            }

        with self._connection() as conn:
            existing = conn.execute(
                "SELECT * FROM documents WHERE path = ?", (str(path),)
            ).fetchone()

        if (
            existing is not None
            and int(existing["size_bytes"]) == stat.st_size
            and int(existing["mtime_ns"]) == stat.st_mtime_ns
        ):
            return {
                "path": str(path),
                "status": "unchanged",
                "chunks": int(existing["chunk_count"]),
            }

        text, error = self._read_text(path)
        if text is None:
            return {"path": str(path), "status": "skipped", "reason": error or "unreadable"}

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if existing is not None and existing["content_hash"] == content_hash:
            with self._connection() as conn:
                conn.execute(
                    """
                    UPDATE documents
                    SET size_bytes=?, mtime_ns=?, indexed_at=?
                    WHERE id=?
                    """,
                    (stat.st_size, stat.st_mtime_ns, _now(), existing["id"]),
                )
            return {
                "path": str(path),
                "status": "unchanged",
                "chunks": int(existing["chunk_count"]),
            }

        chunks = self._chunks(text)
        now = _now()
        with self._connection() as conn:
            if existing is None:
                cursor = conn.execute(
                    """
                    INSERT INTO documents(
                        path, title, content_hash, size_bytes, mtime_ns, indexed_at, chunk_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(path), path.name, content_hash, stat.st_size, stat.st_mtime_ns,
                        now, len(chunks),
                    ),
                )
                document_id = int(cursor.lastrowid)
                status = "indexed"
            else:
                document_id = int(existing["id"])
                conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
                conn.execute(
                    """
                    UPDATE documents
                    SET title=?, content_hash=?, size_bytes=?, mtime_ns=?, indexed_at=?, chunk_count=?
                    WHERE id=?
                    """,
                    (
                        path.name, content_hash, stat.st_size, stat.st_mtime_ns,
                        now, len(chunks), document_id,
                    ),
                )
                status = "updated"

            for chunk_index, (start_line, end_line, content) in enumerate(chunks):
                cursor = conn.execute(
                    """
                    INSERT INTO chunks(
                        document_id, chunk_index, start_line, end_line, content
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (document_id, chunk_index, start_line, end_line, content),
                )
                chunk_id = int(cursor.lastrowid)
                frequencies = Counter(self._tokens(content))
                if frequencies:
                    conn.executemany(
                        "INSERT INTO terms(chunk_id, term, frequency) VALUES (?, ?, ?)",
                        [
                            (chunk_id, term, frequency)
                            for term, frequency in frequencies.items()
                        ],
                    )

        return {"path": str(path), "status": status, "chunks": len(chunks)}

    def index_path(
        self,
        path: str | Path,
        *,
        recursive: bool = True,
        remember_root: bool = True,
    ) -> dict[str, Any]:
        root = self._normalize(path)
        if not root.exists():
            raise FileNotFoundError(f"Knowledge path does not exist: {root}")
        if remember_root:
            self._remember_root(root, recursive)

        summary: dict[str, Any] = {
            "root": str(root),
            "scanned": 0,
            "indexed": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
            "errors": 0,
            "results": [],
        }
        for file_path in self._iter_files(root, recursive):
            summary["scanned"] += 1
            result = self._index_file(file_path.resolve())
            status = str(result["status"])
            if status in summary:
                summary[status] += 1
            elif status == "error":
                summary["errors"] += 1
            summary["results"].append(result)
        return summary

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeHit]:
        terms = list(dict.fromkeys(self._tokens(query)))[:12]
        if not terms:
            return []
        placeholders = ",".join("?" for _ in terms)
        candidate_limit = max(10, int(limit) * 5)
        sql = f"""
            SELECT
                c.id,
                c.chunk_index,
                c.start_line,
                c.end_line,
                c.content,
                d.path,
                d.title,
                SUM(t.frequency) AS term_frequency,
                COUNT(DISTINCT t.term) AS matched_terms
            FROM terms t
            JOIN chunks c ON c.id = t.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE t.term IN ({placeholders})
            GROUP BY c.id
            ORDER BY matched_terms DESC, term_frequency DESC
            LIMIT ?
        """
        params: list[Any] = [*terms, candidate_limit]
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        phrase = query.strip().lower()
        hits: list[KnowledgeHit] = []
        for row in rows:
            matched = int(row["matched_terms"])
            frequency = int(row["term_frequency"])
            coverage = matched / max(1, len(terms))
            phrase_bonus = 2.0 if phrase and phrase in row["content"].lower() else 0.0
            score = coverage * 10.0 + min(frequency, 20) * 0.1 + phrase_bonus
            hits.append(
                KnowledgeHit(
                    source_path=row["path"],
                    title=row["title"],
                    chunk_index=int(row["chunk_index"]),
                    start_line=int(row["start_line"]),
                    end_line=int(row["end_line"]),
                    score=score,
                    content=row["content"],
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[: max(1, int(limit))]

    def read_source(
        self,
        source_path: str | Path,
        *,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> dict[str, Any]:
        path = self._normalize(source_path)
        with self._connection() as conn:
            row = conn.execute(
                "SELECT path, title FROM documents WHERE path = ?", (str(path),)
            ).fetchone()
        if row is None:
            raise PermissionError("Source is not part of the approved knowledge index")
        if not path.exists():
            raise FileNotFoundError(f"Indexed source no longer exists: {path}")

        text, error = self._read_text(path)
        if text is None:
            raise OSError(error or f"Could not read {path}")
        lines = text.splitlines()
        start = max(1, int(start_line))
        requested_end = int(end_line) if end_line is not None else start + 79
        end = min(len(lines), max(start, min(requested_end, start + 199)))
        content = "\n".join(lines[start - 1 : end])
        return {
            "source_path": str(path),
            "source_ref": f"{path}#L{start}-L{end}",
            "title": row["title"],
            "start_line": start,
            "end_line": end,
            "content": content,
        }

    def list_sources(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT path, title, size_bytes, indexed_at, chunk_count
                FROM documents
                ORDER BY indexed_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _prune_missing(self) -> int:
        with self._connection() as conn:
            rows = conn.execute("SELECT id, path FROM documents").fetchall()
            missing = [
                int(row["id"])
                for row in rows
                if not Path(row["path"]).exists()
            ]
            if missing:
                conn.executemany(
                    "DELETE FROM documents WHERE id = ?",
                    [(document_id,) for document_id in missing],
                )
        return len(missing)

    def refresh(self) -> dict[str, Any]:
        with self._connection() as conn:
            roots = conn.execute(
                "SELECT path, recursive FROM roots ORDER BY id"
            ).fetchall()

        aggregate = {
            "roots": len(roots),
            "scanned": 0,
            "indexed": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
            "errors": 0,
            "missing_roots": [],
        }
        for row in roots:
            root = Path(row["path"])
            if not root.exists():
                aggregate["missing_roots"].append(str(root))
                continue
            summary = self.index_path(
                root,
                recursive=bool(row["recursive"]),
                remember_root=False,
            )
            for key in ("scanned", "indexed", "updated", "unchanged", "skipped", "errors"):
                aggregate[key] += int(summary[key])
        aggregate["pruned_missing"] = self._prune_missing()
        return aggregate

    def remove_root(
        self,
        path: str | Path,
        *,
        remove_documents: bool = True,
    ) -> dict[str, Any]:
        root = self._normalize(path)
        with self._connection() as conn:
            deleted_root = conn.execute(
                "DELETE FROM roots WHERE path = ?", (str(root),)
            ).rowcount
            removed_documents = 0
            if remove_documents:
                rows = conn.execute("SELECT id, path FROM documents").fetchall()
                to_remove = []
                for row in rows:
                    document_path = Path(row["path"])
                    if document_path == root or root in document_path.parents:
                        to_remove.append(int(row["id"]))
                if to_remove:
                    conn.executemany(
                        "DELETE FROM documents WHERE id = ?",
                        [(document_id,) for document_id in to_remove],
                    )
                    removed_documents = len(to_remove)
        return {
            "root": str(root),
            "root_removed": bool(deleted_root),
            "indexed_documents_removed": removed_documents,
            "original_files_deleted": False,
        }

    def status(self) -> dict[str, Any]:
        with self._connection() as conn:
            document_count = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            chunk_count = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            term_count = int(conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0])
            root_count = int(conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0])
        return {
            "database": str(self.db_path),
            "roots": root_count,
            "documents": document_count,
            "chunks": chunk_count,
            "terms": term_count,
        }
