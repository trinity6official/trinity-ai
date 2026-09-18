from types import SimpleNamespace

from core.attachments import AttachmentService


class FakeHost:
    def __init__(self):
        self.sent = []
        self.history = []
        self._conversation_history = []

    def respond(self, message):
        self.sent.append(message)

    def _save_to_history(self, user, assistant):
        self.history.append((user, assistant))

    def get_llm_for_task(self, question):
        return object()

    def _invoke_with_failover(self, messages, preferred_llm=None):
        return SimpleNamespace(content="document analysis")


class FakeVision:
    def available(self):
        return True

    def analyze(self, image_bytes, question, media_type):
        assert image_bytes == b"image"
        assert media_type == "image/png"
        return "vision result"


def test_photo_uses_local_vision_and_history():
    host = FakeHost()
    service = AttachmentService(host, lambda _file_id: ("photos/test.png", b"image"), vision=FakeVision())
    service.handle_photo([{"file_id": "x", "file_size": 10}], "what is this?")
    assert host.sent == ["Looking at your image locally...", "vision result"]
    assert host.history[-1] == ("[photo] what is this?", "vision result")


def test_photo_without_vision_is_honest():
    host = FakeHost()
    service = AttachmentService(host, lambda _file_id: ("photos/test.png", b"image"), vision=None)
    service.handle_photo([{"file_id": "x"}], "")
    assert "local vision is not configured" in host.sent[-1]


def test_text_document_is_analyzed():
    host = FakeHost()

    service = AttachmentService(
        host, lambda _file_id: ("docs/readme.md", b"hello from trinity")
    )
    service.handle_document(
        {"file_id": "doc", "file_name": "readme.md", "mime_type": "text/markdown"},
        "summarize",
    )
    assert host.sent[0] == "Reading readme.md..."
    assert host.sent[-1] == "document analysis"
    assert host.history[-1][0].startswith("[document: readme.md]")


def test_unknown_document_type_is_rejected_without_llm():
    host = FakeHost()

    service = AttachmentService(
        host, lambda _file_id: ("docs/file.bin", b"\x00\x01")
    )
    service.handle_document(
        {"file_id": "doc", "file_name": "file.bin", "mime_type": "application/octet-stream"}
    )
    assert "can't read that file type" in host.sent[-1]
    assert host.history == []
