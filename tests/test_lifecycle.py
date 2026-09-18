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
        self.persistence = SimpleNamespace(
            save=lambda: SimpleNamespace(success=True, brain_path="memory", error=None)
        )

    def respond(self, message):
        self.calls.append(("respond", message))


def test_shutdown_stops_daemon_and_persists():
    host = Host()
    host.daemon = SimpleNamespace(stop=lambda: host.calls.append(("daemon_stop",)))
    RuntimeLoop(host).shutdown()
    assert ("daemon_stop",) in host.calls
    assert ("shutdown",) in host.calls


def test_health_warning_uses_channel_neutral_response_fallback():
    host = Host()
    RuntimeLoop(host).health_warning(["high memory", "model offline"])
    kind, message = host.calls[-1]
    assert kind == "respond"
    assert "high memory" in message
    assert "model offline" in message


def test_health_warning_prefers_notification_boundary():
    host = Host()
    delivered = []
    host.notify = lambda message, **kwargs: delivered.append((message, kwargs))
    RuntimeLoop(host).health_warning(["model offline"])
    assert delivered[0][1] == {"category": "health", "urgent": True}
    assert not [call for call in host.calls if call[0] == "respond"]
