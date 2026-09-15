import json
from types import SimpleNamespace

from core.audit import ActionAuditTrail
from core.events import EventBus
from core.perception import PerceptionService


class FakeComputer:
    def __init__(self, image=b"SECRET_SCREEN_BYTES"):
        self.image = image
        self.captures = 0

    def capture_screen(self):
        self.captures += 1
        return SimpleNamespace(success=True, image=self.image, error=None, media_type="image/png")

    def frontmost_app(self):
        return SimpleNamespace(success=True, output="Terminal")


class FakeVision:
    def __init__(self, available=True):
        self._available = available
        self.calls = []

    def available(self):
        return self._available

    def analyze(self, image, prompt, media_type):
        self.calls.append((image, prompt, media_type))
        return "SENSITIVE MODEL DESCRIPTION"


def test_screen_perception_connects_capture_to_local_vision(tmp_path):
    vision = FakeVision()
    service = PerceptionService(FakeComputer(), vision)
    result = service.analyze_screen("Find the error")
    assert result.success is True
    assert result.description == "SENSITIVE MODEL DESCRIPTION"
    assert result.app_context == "Terminal"
    image, prompt, media = vision.calls[0]
    assert image == b"SECRET_SCREEN_BYTES"
    assert "Frontmost application: Terminal" in prompt
    assert media == "image/png"


def test_perception_does_not_persist_raw_screen_or_description(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    bus = EventBus(); events=[]; bus.subscribe("*", events.append)
    service = PerceptionService(
        FakeComputer(), FakeVision(),
        event_bus=bus,
        audit_trail=ActionAuditTrail(audit_path),
    )
    result = service.analyze_screen()
    assert result.success
    audit_text = audit_path.read_text()
    assert "SECRET_SCREEN_BYTES" not in audit_text
    assert "SENSITIVE MODEL DESCRIPTION" not in audit_text
    assert all("SENSITIVE MODEL DESCRIPTION" not in str(event.payload) for event in events)
    completed = [json.loads(line) for line in audit_text.splitlines() if '"status": "completed"' in line]
    assert completed[-1]["result"]["description_chars"] == len("SENSITIVE MODEL DESCRIPTION")


def test_unavailable_vision_fails_before_screen_capture():
    class NoCapture(FakeComputer):
        def capture_screen(self):
            raise AssertionError("screen should not be captured without a local vision model")
    result = PerceptionService(NoCapture(), FakeVision(False)).analyze_screen()
    assert result.success is False
    assert "unavailable" in result.error.lower()


def test_perception_updates_in_memory_context_without_exposing_description(tmp_path):
    contexts = []
    bus = EventBus(); events=[]; bus.subscribe("*", events.append)
    service = PerceptionService(
        FakeComputer(), FakeVision(), event_bus=bus,
        context_sink=lambda app, description: contexts.append((app, description)),
    )
    assert service.analyze_screen().success
    assert contexts == [("Terminal", "SENSITIVE MODEL DESCRIPTION")]
    assert all("SENSITIVE MODEL DESCRIPTION" not in str(event.payload) for event in events)


def test_perception_skips_unchanged_screen_unless_forced():
    vision = FakeVision()
    service = PerceptionService(FakeComputer(b"same"), vision)
    first = service.analyze_screen()
    second = service.analyze_screen()
    forced = service.analyze_screen(force=True)
    assert first.success and not first.skipped
    assert second.success and second.skipped and second.reason == "unchanged"
    assert forced.success and not forced.skipped
    assert len(vision.calls) == 2
