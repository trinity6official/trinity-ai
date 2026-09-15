from pathlib import Path

import pytest

from core.knowledge_index import KnowledgeIndex


def make_index(tmp_path):
    return KnowledgeIndex(
        tmp_path / "knowledge.db",
        chunk_chars=80,
        overlap_lines=1,
        max_file_bytes=100_000,
    )


def test_index_and_search_return_source_line_references(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "phoenix.md"
    source.write_text(
        "# Phoenix\n\nPhoenix is a Python automation project.\nIt uses local-first architecture.\n",
        encoding="utf-8",
    )
    index = make_index(tmp_path)

    summary = index.index_path(docs)
    hits = index.search("Python automation")

    assert summary["indexed"] == 1
    assert hits
    assert hits[0].source_path == str(source.resolve())
    assert "#L" in hits[0].source_ref
    assert "Python automation" in hits[0].content


def test_unchanged_file_is_incremental_noop(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("alpha beta gamma", encoding="utf-8")
    index = make_index(tmp_path)

    first = index.index_path(source)
    second = index.index_path(source)

    assert first["indexed"] == 1
    assert second["unchanged"] == 1
    assert index.status()["documents"] == 1


def test_modified_file_replaces_old_terms(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("oldterm only", encoding="utf-8")
    index = make_index(tmp_path)
    index.index_path(source)

    source.write_text("newterm only and different size", encoding="utf-8")
    result = index.index_path(source)

    assert result["updated"] == 1
    assert index.search("oldterm") == []
    assert index.search("newterm")


def test_refresh_discovers_new_files_inside_approved_root(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "one.md").write_text("first document", encoding="utf-8")
    index = make_index(tmp_path)
    index.index_path(docs)

    (docs / "two.md").write_text("second unique document", encoding="utf-8")
    refreshed = index.refresh()

    assert refreshed["indexed"] == 1
    assert index.status()["documents"] == 2
    assert index.search("unique")


def test_refresh_prunes_deleted_sources(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "gone.md"
    source.write_text("temporary knowledge", encoding="utf-8")
    index = make_index(tmp_path)
    index.index_path(docs)
    source.unlink()

    refreshed = index.refresh()

    assert refreshed["pruned_missing"] == 1
    assert index.search("temporary") == []


def test_directory_scan_ignores_hidden_and_unsupported_files(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "good.md").write_text("searchable good content", encoding="utf-8")
    (docs / "image.png").write_bytes(b"\x89PNG")
    hidden = docs / ".secret"
    hidden.mkdir()
    (hidden / "secret.md").write_text("should not index", encoding="utf-8")
    index = make_index(tmp_path)

    index.index_path(docs)

    sources = index.list_sources()
    assert len(sources) == 1
    assert sources[0]["title"] == "good.md"


def test_read_source_only_allows_indexed_files(tmp_path):
    indexed = tmp_path / "indexed.md"
    indexed.write_text("line one\nline two\nline three\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("private", encoding="utf-8")
    index = make_index(tmp_path)
    index.index_path(indexed)

    result = index.read_source(indexed, start_line=2, end_line=3)
    assert result["content"] == "line two\nline three"
    assert result["source_ref"].endswith("#L2-L3")

    with pytest.raises(PermissionError):
        index.read_source(outside)


def test_remove_root_removes_index_not_original_file(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "keep.md"
    source.write_text("keep original", encoding="utf-8")
    index = make_index(tmp_path)
    index.index_path(docs)

    result = index.remove_root(docs)

    assert result["root_removed"] is True
    assert result["indexed_documents_removed"] == 1
    assert result["original_files_deleted"] is False
    assert source.exists()
    assert index.status()["documents"] == 0
