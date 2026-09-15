import sys
from types import SimpleNamespace

from core.document_ingestion import DocumentExtractor


def test_pdf_extraction_preserves_page_references(tmp_path, monkeypatch):
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"fake pdf")

    class FakePage:
        def __init__(self, text):
            self._text = text
        def extract_text(self):
            return self._text

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage("intro page"), FakePage("Phoenix architecture details")]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))
    extractor = DocumentExtractor(chunk_chars=500)
    chunks = extractor.extract(source)

    assert chunks[1].locator_kind == "page"
    assert chunks[1].source_ref(source).endswith("#p2")
    assert "Phoenix" in chunks[1].content

    read = extractor.read_reference(f"{source}#p2")
    assert read["source_ref"].endswith("#p2")
    assert "Phoenix architecture" in read["content"]


def test_docx_extraction_preserves_paragraph_references(tmp_path, monkeypatch):
    source = tmp_path / "proposal.docx"
    source.write_bytes(b"fake docx")

    class FakeDocument:
        def __init__(self, _path):
            self.paragraphs = [
                SimpleNamespace(text="Heading"),
                SimpleNamespace(text="Phoenix uses Python"),
            ]
            self.tables = []

    monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=FakeDocument))
    extractor = DocumentExtractor(chunk_chars=500)
    chunks = extractor.extract(source)

    assert chunks[1].locator_kind == "paragraph"
    assert chunks[1].source_ref(source).endswith("#P2")

    read = extractor.read_reference(f"{source}#P2")
    assert read["source_ref"].endswith("#P2")
    assert read["content"] == "Phoenix uses Python"
