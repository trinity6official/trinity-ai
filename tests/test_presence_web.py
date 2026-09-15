import json
from urllib.request import urlopen

from core.awareness import AwarenessEngine
from core.events import EventBus
from core.presence import PresenceEngine
from core.presence_web import PresenceServer


def test_presence_server_exposes_local_state_and_ui():
    bus = EventBus(); awareness = AwarenessEngine(bus); presence = PresenceEngine(bus)
    awareness.update_visual_context("Terminal", "private description")
    bus.publish("message.received", text="hi")
    server = PresenceServer(presence, awareness=awareness, port=0)
    assert server.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.port}/api/presence", timeout=2) as response:
            data = json.loads(response.read())
        assert data["state"] == "thinking"
        assert data["frontmost_app"] == "Terminal"
        assert "private description" not in json.dumps(data)
        with urlopen(f"http://127.0.0.1:{server.port}/", timeout=2) as response:
            html = response.read().decode()
        assert "TRINITY" in html
        assert "/api/presence" in html
    finally:
        server.stop()


def test_presence_server_refuses_non_loopback_binding():
    bus = EventBus(); presence = PresenceEngine(bus)
    server = PresenceServer(presence, host="0.0.0.0", port=0)
    assert server.start() is False
