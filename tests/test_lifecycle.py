from types import SimpleNamespace

from core.lifecycle import RuntimeLoop


class Host:
    def __init__(self):
        self.calls = []
        self.daemon = None
        self.consciousness = SimpleNamespace(
            remember=lambda *a, **k: self.calls.append(("remember", a, k)),
            shutdown=lambda: self.calls.append(("shutdown",)),
        )

    def handle_message(self, text, chat_id):
        self.calls.append(("text", text, chat_id))

    def handle_photo_message(self, photos, caption, chat_id):
        self.calls.append(("photo", photos, caption, chat_id))

    def handle_document_message(self, doc, caption, chat_id):
        self.calls.append(("document", doc, caption, chat_id))

    def send_telegram(self, message):
        self.calls.append(("send", message))

    def _commit_brain(self):
        self.calls.append(("persist",))

    def _handle_health_warning(self, warnings):
        pass


def test_dispatch_text_photo_and_document():
    host = Host()
    loop = RuntimeLoop(host)
    loop.dispatch_update({"message": {"chat": {"id": 1}, "text": "hello"}})
    loop.dispatch_update({"message": {"chat": {"id": 1}, "photo": [{"file_id": "p"}], "caption": "c"}})
    loop.dispatch_update({"message": {"chat": {"id": 1}, "document": {"file_id": "d", "file_name": "a.txt", "mime_type": "text/plain"}}})
    assert host.calls[0] == ("text", "hello", "1")
    assert host.calls[1][0] == "photo"
    assert host.calls[2][0] == "document"


def test_image_document_routes_to_photo():
    host = Host()
    loop = RuntimeLoop(host)
    loop.dispatch_update({
        "message": {
            "chat": {"id": 1},
            "document": {"file_id": "d", "file_name": "screen.png", "mime_type": "image/png", "file_size": 9},
        }
    })
    assert host.calls[0][0] == "photo"
    assert host.calls[0][1] == [{"file_id": "d", "file_size": 9}]


def test_shutdown_stops_daemon_and_persists():
    host = Host()
    host.daemon = SimpleNamespace(stop=lambda: host.calls.append(("daemon_stop",)))
    RuntimeLoop(host).shutdown()
    assert ("daemon_stop",) in host.calls
    assert ("shutdown",) in host.calls
    assert ("persist",) in host.calls


def test_health_warning_formats_message():
    host = Host()
    RuntimeLoop(host).health_warning(["high memory", "model offline"])
    assert "high memory" in host.calls[-1][1]
    assert "model offline" in host.calls[-1][1]
