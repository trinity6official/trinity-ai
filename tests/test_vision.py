from core.vision import LocalVisionService


class FakeVision:
    name = "fake"
    def __init__(self, available=True): self._available = available; self.calls = []
    def available(self): return self._available
    def analyze(self, image, prompt, media_type="image/jpeg"):
        self.calls.append((image, prompt, media_type)); return "I see a diagram"


def test_vision_service_reports_provider_availability():
    assert LocalVisionService(FakeVision(True)).available() is True
    assert LocalVisionService(FakeVision(False)).available() is False
    assert LocalVisionService(None).available() is False


def test_vision_service_delegates_analysis():
    provider = FakeVision()
    service = LocalVisionService(provider)
    assert service.analyze(b"img", "describe", "image/png") == "I see a diagram"
    assert provider.calls == [(b"img", "describe", "image/png")]


def test_unconfigured_vision_fails_clearly():
    try:
        LocalVisionService(None).analyze(b"img", "describe")
    except RuntimeError as exc:
        assert "TRINITY_VISION_MODEL" in str(exc)
    else:
        raise AssertionError("Expected unconfigured vision to fail")
