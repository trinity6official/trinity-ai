import sys
from types import SimpleNamespace

from core.knowledge_index import KnowledgeIndex


def test_pdf_is_indexed_and_search_returns_page_reference(tmp_path, monkeypatch):
    source = tmp_path / "architecture.pdf"
    source.write_bytes(b"fake pdf")

    class FakePage:
        def __init__(self, text):
            self._text = text
        def extract_text(self):
            return self._text

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage("overview"), FakePage("DriftGuard remediation engine")]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))
    index = KnowledgeIndex(
        tmp_path / "knowledge.db",
        auto_embedding_provider=False,
    )

    summary = index.index_path(source)
    hits = index.search("remediation engine")

    assert summary["indexed"] == 1
    assert hits
    assert hits[0].source_ref.endswith("#p2")
    read = index.read_reference(hits[0].source_ref)
    assert "DriftGuard" in read["content"]


def test_docx_is_indexed_and_search_returns_paragraph_reference(tmp_path, monkeypatch):
    source = tmp_path / "proposal.docx"
    source.write_bytes(b"fake docx")

    class FakeDocument:
        def __init__(self, _path):
            self.paragraphs = [
                SimpleNamespace(text="Summary"),
                SimpleNamespace(text="Phoenix primary language is Python"),
            ]
            self.tables = []

    monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=FakeDocument))
    index = KnowledgeIndex(
        tmp_path / "knowledge.db",
        auto_embedding_provider=False,
    )

    index.index_path(source)
    hits = index.search("Phoenix Python")

    assert hits
    assert hits[0].source_ref.endswith("#P2")
    assert index.list_sources()[0]["document_type"] == "docx"
