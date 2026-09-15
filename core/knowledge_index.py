"""Local personal-knowledge index for Trinity.

The index remains fully usable without embeddings. Text/code uses line
references, PDF uses page references, and DOCX uses paragraph references.
Optional local embeddings add hybrid search while lexical search stays the
portable Android-safe fallback.
"""
from __future__ import annotations

from array import array
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

from core.document_ingestion import (
    DocumentExtractor,
    ExtractedChunk,
    SUPPORTED_NAMES,
    SUPPORTED_SUFFIXES,
)
from core.knowledge_embeddings import EmbeddingProvider, build_embedding_provider_from_env


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_TOKEN_RE = re.compile(r"[\w.-]+", re.UNICODE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with",
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
    locator_kind: str = "line"
    lexical_score: float | None = None
    semantic_score: float | None = None

    @property
    def source_ref(self) -> str:
        if self.locator_kind == "page":
            if self.start_line == self.end_line:
                return f"{self.source_path}#p{self.start_line}"
            return f"{self.source_path}#p{self.start_line}-p{self.end_line}"
        if self.locator_kind == "paragraph":
            if self.start_line == self.end_line:
                return f"{self.source_path}#P{self.start_line}"
            return f"{self.source_path}#P{self.start_line}-P{self.end_line}"
        return f"{self.source_path}#L{self.start_line}-L{self.end_line}"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "source_path": self.source_path,
            "source_ref": self.source_ref,
            "title": self.title,
            "chunk_index": self.chunk_index,
            "locator_kind": self.locator_kind,
            # Preserve old field names for compatibility with v1 callers/tests.
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_locator": self.start_line,
            "end_locator": self.end_line,
            "score": round(self.score, 4),
            "content": self.content,
        }
        if self.lexical_score is not None:
            data["lexical_score"] = round(self.lexical_score, 4)
        if self.semantic_score is not None:
            data["semantic_score"] = round(self.semantic_score, 4)
        return data


class KnowledgeIndex:
    """Incremental local index with lexical search and optional hybrid embeddings."""

    def __init__(
        self,
        db_path: str | Path = "memory/knowledge_index.db",
        *,
        chunk_chars: int = 1600,
        overlap_lines: int = 2,
        max_file_bytes: int = 20_000_000,
        max_files_per_scan: int = 5000,
        embedding_provider: EmbeddingProvider | None = None,
        auto_embedding_provider: bool = True,
        embedding_batch_size: int = 16,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.chunk_chars = max(400, int(chunk_chars))
        self.overlap_lines = max(0, int(overlap_lines))
        self.max_file_bytes = max(1024, int(max_file_bytes))
        self.max_files_per_scan = max(1, int(max_files_per_scan))
        self.embedding_batch_size = max(1, min(int(embedding_batch_size), 128))
        self.extractor = DocumentExtractor(
            chunk_chars=self.chunk_chars,
            overlap_lines=self.overlap_lines,
        )
        if embedding_provider is not None:
            self.embedding_provider = embedding_provider
            self.embedding_provider_error: str | None = None
        elif auto_embedding_provider:
            try:
                self.embedding_provider = build_embedding_provider_from_env()
                self.embedding_provider_error = None
            except Exception as exc:
                # Embeddings are an enhancement. Failure must never disable the
                # portable lexical knowledge path.
                self.embedding_provider = None
                self.embedding_provider_error = str(exc)
        else:
            self.embedding_provider = None
            self.embedding_provider_error = None
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

                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
                    provider_key TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    vector BLOB NOT NULL,
                    embedded_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_terms_term ON terms(term);
                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_knowledge_documents_path ON documents(path);
                CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_provider
                    ON chunk_embeddings(provider_key);
                """
            )
            chunk_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(chunks)").fetchall()
            }
            if "locator_kind" not in chunk_columns:
                conn.execute(
                    "ALTER TABLE chunks ADD COLUMN locator_kind TEXT NOT NULL DEFAULT 'line'"
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
        return path.suffix.lower() in SUPPORTED_SUFFIXES or path.name.lower() in SUPPORTED_NAMES

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
        """Compatibility helper for line-based text files."""
        try:
            size = path.stat().st_size
        except OSError as exc:
            return None, str(exc)
        if size > self.max_file_bytes:
            return None, f"file exceeds {self.max_file_bytes} bytes"
        if path.suffix.lower() in {".pdf", ".docx"}:
            return None, "rich document uses structured extraction"
        try:
            return self.extractor._decode_text(path.read_bytes()), None
        except (OSError, ValueError) as exc:
            return None, str(exc)

    def _chunks(self, text: str) -> list[tuple[int, int, str]]:
        """Compatibility helper retained for existing tests/callers."""
        return [
            (chunk.start_locator, chunk.end_locator, chunk.content)
            for chunk in self.extractor._line_chunks(text)
        ]

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

    @staticmethod
    def _hash_chunks(chunks: list[ExtractedChunk]) -> str:
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(chunk.locator_kind.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(chunk.start_locator).encode("ascii"))
            digest.update(b"\0")
            digest.update(str(chunk.end_locator).encode("ascii"))
            digest.update(b"\0")
            digest.update(chunk.content.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _extract_file(self, path: Path) -> tuple[list[ExtractedChunk] | None, str | None]:
        try:
            return self.extractor.extract(path), None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _pack_vector(vector: list[float]) -> bytes:
        return array("f", [float(value) for value in vector]).tobytes()

    @staticmethod
    def _unpack_vector(blob: bytes, dimensions: int) -> list[float]:
        values = array("f")
        values.frombytes(blob)
        if len(values) != dimensions:
            raise ValueError("stored embedding dimensions do not match vector bytes")
        return [float(value) for value in values]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a <= 0.0 or norm_b <= 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _embed_rows(self, rows: list[sqlite3.Row]) -> dict[str, Any]:
        provider = self.embedding_provider
        if provider is None or not rows:
            return {"embedded": 0, "embedding_error": self.embedding_provider_error}

        embedded = 0
        try:
            for offset in range(0, len(rows), self.embedding_batch_size):
                batch = rows[offset : offset + self.embedding_batch_size]
                vectors = provider.embed([str(row["content"]) for row in batch])
                if len(vectors) != len(batch):
                    raise RuntimeError("embedding provider returned an unexpected vector count")
                payload = []
                for row, vector in zip(batch, vectors):
                    if not vector:
                        continue
                    payload.append(
                        (
                            int(row["id"]),
                            provider.key,
                            len(vector),
                            self._pack_vector(vector),
                            _now(),
                        )
                    )
                if payload:
                    with self._connection() as conn:
                        conn.executemany(
                            """
                            INSERT INTO chunk_embeddings(
                                chunk_id, provider_key, dimensions, vector, embedded_at
                            ) VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(chunk_id) DO UPDATE SET
                                provider_key=excluded.provider_key,
                                dimensions=excluded.dimensions,
                                vector=excluded.vector,
                                embedded_at=excluded.embedded_at
                            """,
                            payload,
                        )
                    embedded += len(payload)
            self.embedding_provider_error = None
            return {"embedded": embedded, "embedding_error": None}
        except Exception as exc:
            self.embedding_provider_error = str(exc)
            return {"embedded": embedded, "embedding_error": str(exc)}

    def refresh_embeddings(self, *, limit: int | None = None) -> dict[str, Any]:
        provider = self.embedding_provider
        if provider is None:
            return {
                "enabled": False,
                "provider": None,
                "embedded": 0,
                "pending": 0,
                "error": self.embedding_provider_error,
            }

        sql = """
            SELECT c.id, c.content
            FROM chunks c
            LEFT JOIN chunk_embeddings e ON e.chunk_id = c.id
            WHERE e.chunk_id IS NULL OR e.provider_key != ?
            ORDER BY c.id
        """
        params: list[Any] = [provider.key]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = self._embed_rows(rows)
        with self._connection() as conn:
            pending = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM chunks c
                    LEFT JOIN chunk_embeddings e ON e.chunk_id = c.id
                    WHERE e.chunk_id IS NULL OR e.provider_key != ?
                    """,
                    (provider.key,),
                ).fetchone()[0]
            )
        return {
            "enabled": True,
            "provider": provider.key,
            "embedded": int(result.get("embedded", 0)),
            "pending": pending,
            "error": result.get("embedding_error"),
        }

    def _index_file(self, path: Path) -> dict[str, Any]:
        try:
            stat = path.stat()
        except OSError as exc:
            return {"path": str(path), "status": "error", "reason": str(exc)}

        if not self._supported(path):
            return {"path": str(path), "status": "skipped", "reason": "unsupported file type"}
        if stat.st_size > self.max_file_bytes:
            return {
                "path": str(path), "status": "skipped",
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
                "path": str(path), "status": "unchanged",
                "chunks": int(existing["chunk_count"]),
            }

        chunks, error = self._extract_file(path)
        if chunks is None:
            return {"path": str(path), "status": "skipped", "reason": error or "unreadable"}

        content_hash = self._hash_chunks(chunks)
        if existing is not None and existing["content_hash"] == content_hash:
            with self._connection() as conn:
                conn.execute(
                    """UPDATE documents SET size_bytes=?, mtime_ns=?, indexed_at=? WHERE id=?""",
                    (stat.st_size, stat.st_mtime_ns, _now(), existing["id"]),
                )
            return {
                "path": str(path), "status": "unchanged",
                "chunks": int(existing["chunk_count"]),
            }

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
                        str(path), path.name, content_hash, stat.st_size,
                        stat.st_mtime_ns, now, len(chunks),
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

            for chunk_index, chunk in enumerate(chunks):
                cursor = conn.execute(
                    """
                    INSERT INTO chunks(
                        document_id, chunk_index, start_line, end_line, content, locator_kind
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id, chunk_index, chunk.start_locator,
                        chunk.end_locator, chunk.content, chunk.locator_kind,
                    ),
                )
                chunk_id = int(cursor.lastrowid)
                frequencies = Counter(self._tokens(chunk.content))
                if frequencies:
                    conn.executemany(
                        "INSERT INTO terms(chunk_id, term, frequency) VALUES (?, ?, ?)",
                        [(chunk_id, term, frequency) for term, frequency in frequencies.items()],
                    )

        embedding = self.refresh_embeddings()
        result = {"path": str(path), "status": status, "chunks": len(chunks)}
        if embedding.get("error"):
            result["embedding_error"] = embedding["error"]
        return result

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
            "root": str(root), "scanned": 0, "indexed": 0, "updated": 0,
            "unchanged": 0, "skipped": 0, "errors": 0, "results": [],
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

    def _lexical_rows(self, query: str, limit: int) -> list[sqlite3.Row]:
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
                c.locator_kind,
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
        with self._connection() as conn:
            return conn.execute(sql, [*terms, candidate_limit]).fetchall()

    def _semantic_rows(self, query: str, limit: int) -> list[tuple[sqlite3.Row, float]]:
        provider = self.embedding_provider
        if provider is None:
            return []
        try:
            vectors = provider.embed([query])
            if not vectors or not vectors[0]:
                return []
            query_vector = vectors[0]
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT c.id, c.chunk_index, c.start_line, c.end_line,
                           c.locator_kind, c.content, d.path, d.title,
                           e.dimensions, e.vector
                    FROM chunk_embeddings e
                    JOIN chunks c ON c.id = e.chunk_id
                    JOIN documents d ON d.id = c.document_id
                    WHERE e.provider_key = ?
                    """,
                    (provider.key,),
                ).fetchall()
            minimum_score = float(
                os.environ.get("TRINITY_KNOWLEDGE_SEMANTIC_MIN_SCORE", "0.20")
            )
            scored: list[tuple[sqlite3.Row, float]] = []
            for row in rows:
                try:
                    vector = self._unpack_vector(row["vector"], int(row["dimensions"]))
                    score = self._cosine(query_vector, vector)
                except Exception:
                    continue
                if score >= minimum_score:
                    scored.append((row, score))
            scored.sort(key=lambda pair: pair[1], reverse=True)
            return scored[: max(10, int(limit) * 5)]
        except Exception as exc:
            self.embedding_provider_error = str(exc)
            return []

    @staticmethod
    def _row_to_hit(
        row: sqlite3.Row,
        score: float,
        *,
        lexical_score: float | None = None,
        semantic_score: float | None = None,
    ) -> KnowledgeHit:
        return KnowledgeHit(
            source_path=row["path"], title=row["title"],
            chunk_index=int(row["chunk_index"]),
            start_line=int(row["start_line"]), end_line=int(row["end_line"]),
            locator_kind=str(row["locator_kind"] or "line"),
            score=score, content=row["content"],
            lexical_score=lexical_score, semantic_score=semantic_score,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        mode: str = "hybrid",
    ) -> list[KnowledgeHit]:
        mode = (mode or "hybrid").strip().lower()
        if mode not in {"lexical", "semantic", "hybrid"}:
            raise ValueError("Knowledge search mode must be lexical, semantic, or hybrid")
        limit = max(1, int(limit))

        lexical_rows = [] if mode == "semantic" else self._lexical_rows(query, limit)
        phrase = query.strip().lower()
        terms = list(dict.fromkeys(self._tokens(query)))[:12]
        lexical: dict[int, tuple[sqlite3.Row, float]] = {}
        for row in lexical_rows:
            matched = int(row["matched_terms"])
            frequency = int(row["term_frequency"])
            coverage = matched / max(1, len(terms))
            phrase_bonus = 2.0 if phrase and phrase in row["content"].lower() else 0.0
            score = coverage * 10.0 + min(frequency, 20) * 0.1 + phrase_bonus
            lexical[int(row["id"])] = (row, score)

        semantic_rows = [] if mode == "lexical" else self._semantic_rows(query, limit)
        semantic = {int(row["id"]): (row, score) for row, score in semantic_rows}

        if mode == "lexical" or not semantic:
            hits = [self._row_to_hit(row, score, lexical_score=score) for row, score in lexical.values()]
            hits.sort(key=lambda hit: hit.score, reverse=True)
            return hits[:limit]
        if mode == "semantic":
            hits = [self._row_to_hit(row, score, semantic_score=score) for row, score in semantic.values()]
            hits.sort(key=lambda hit: hit.score, reverse=True)
            return hits[:limit]

        max_lexical = max((score for _, score in lexical.values()), default=1.0)
        combined: list[KnowledgeHit] = []
        for chunk_id in set(lexical) | set(semantic):
            lexical_pair = lexical.get(chunk_id)
            semantic_pair = semantic.get(chunk_id)
            row = lexical_pair[0] if lexical_pair is not None else semantic_pair[0]
            lexical_raw = lexical_pair[1] if lexical_pair is not None else 0.0
            semantic_raw = semantic_pair[1] if semantic_pair is not None else 0.0
            lexical_norm = lexical_raw / max_lexical if max_lexical > 0 else 0.0
            semantic_norm = max(0.0, min(1.0, (semantic_raw + 1.0) / 2.0))
            score = 0.45 * lexical_norm + 0.55 * semantic_norm
            combined.append(
                self._row_to_hit(
                    row, score,
                    lexical_score=lexical_raw if lexical_pair is not None else None,
                    semantic_score=semantic_raw if semantic_pair is not None else None,
                )
            )
        combined.sort(key=lambda hit: hit.score, reverse=True)
        return combined[:limit]

    def read_source(
        self,
        source_path: str | Path,
        *,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> dict[str, Any]:
        raw_source = str(source_path)
        if "#" in raw_source:
            return self.read_reference(raw_source)

        path = self._normalize(source_path)
        with self._connection() as conn:
            row = conn.execute(
                "SELECT path, title FROM documents WHERE path = ?", (str(path),)
            ).fetchone()
        if row is None:
            raise PermissionError("Source is not part of the approved knowledge index")
        if not path.exists():
            raise FileNotFoundError(f"Indexed source no longer exists: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            page = max(1, int(start_line))
            return self.read_reference(f"{path}#p{page}")
        if suffix == ".docx":
            start = max(1, int(start_line))
            end = int(end_line) if end_line is not None else start + 19
            return self.read_reference(f"{path}#P{start}-P{end}")

        text, error = self._read_text(path)
        if text is None:
            raise OSError(error or f"Could not read {path}")
        lines = text.splitlines()
        start = max(1, int(start_line))
        requested_end = int(end_line) if end_line is not None else start + 79
        end = min(len(lines), max(start, min(requested_end, start + 199)))
        content = "\n".join(lines[start - 1 : end])
        return {
            "source_path": str(path), "source_ref": f"{path}#L{start}-L{end}",
            "title": row["title"], "locator_kind": "line",
            "start_line": start, "end_line": end,
            "start_locator": start, "end_locator": end, "content": content,
        }

    def read_reference(self, source_ref: str) -> dict[str, Any]:
        raw_path = source_ref.rsplit("#", 1)[0] if "#" in source_ref else source_ref
        path = self._normalize(raw_path)
        with self._connection() as conn:
            row = conn.execute(
                "SELECT path, title FROM documents WHERE path = ?", (str(path),)
            ).fetchone()
        if row is None:
            raise PermissionError("Source is not part of the approved knowledge index")
        if not path.exists():
            raise FileNotFoundError(f"Indexed source no longer exists: {path}")
        result = self.extractor.read_reference(f"{path}#{source_ref.rsplit('#', 1)[1]}")
        result["title"] = row["title"]
        # Backward-compatible aliases for existing consumers.
        result["start_line"] = result["start_locator"]
        result["end_line"] = result["end_locator"]
        return result

    def list_sources(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT path, title, size_bytes, indexed_at, chunk_count
                FROM documents ORDER BY indexed_at DESC LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["document_type"] = self.extractor.document_type(Path(item["path"]))
            result.append(item)
        return result

    def _prune_missing(self) -> int:
        with self._connection() as conn:
            rows = conn.execute("SELECT id, path FROM documents").fetchall()
            missing = [int(row["id"]) for row in rows if not Path(row["path"]).exists()]
            if missing:
                conn.executemany(
                    "DELETE FROM documents WHERE id = ?",
                    [(document_id,) for document_id in missing],
                )
        return len(missing)

    def refresh(self) -> dict[str, Any]:
        with self._connection() as conn:
            roots = conn.execute("SELECT path, recursive FROM roots ORDER BY id").fetchall()

        aggregate: dict[str, Any] = {
            "roots": len(roots), "scanned": 0, "indexed": 0, "updated": 0,
            "unchanged": 0, "skipped": 0, "errors": 0, "missing_roots": [],
        }
        for row in roots:
            root = Path(row["path"])
            if not root.exists():
                aggregate["missing_roots"].append(str(root))
                continue
            summary = self.index_path(
                root, recursive=bool(row["recursive"]), remember_root=False,
            )
            for key in ("scanned", "indexed", "updated", "unchanged", "skipped", "errors"):
                aggregate[key] += int(summary[key])
        aggregate["pruned_missing"] = self._prune_missing()
        aggregate["embeddings"] = self.refresh_embeddings()
        return aggregate

    def remove_root(
        self,
        path: str | Path,
        *,
        remove_documents: bool = True,
    ) -> dict[str, Any]:
        root = self._normalize(path)
        with self._connection() as conn:
            deleted_root = conn.execute("DELETE FROM roots WHERE path = ?", (str(root),)).rowcount
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
            "root": str(root), "root_removed": bool(deleted_root),
            "indexed_documents_removed": removed_documents,
            "original_files_deleted": False,
        }

    def status(self) -> dict[str, Any]:
        provider = self.embedding_provider.key if self.embedding_provider is not None else None
        with self._connection() as conn:
            document_count = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            chunk_count = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            term_count = int(conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0])
            root_count = int(conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0])
            if provider:
                embedding_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM chunk_embeddings WHERE provider_key = ?",
                        (provider,),
                    ).fetchone()[0]
                )
            else:
                embedding_count = 0
        return {
            "database": str(self.db_path), "roots": root_count,
            "documents": document_count, "chunks": chunk_count, "terms": term_count,
            "supported_rich_documents": ["pdf", "docx"],
            "embedding_provider": provider,
            "embeddings_enabled": self.embedding_provider is not None,
            "embedded_chunks": embedding_count,
            "pending_embeddings": max(0, chunk_count - embedding_count) if provider else 0,
            "embedding_error": self.embedding_provider_error,
        }
