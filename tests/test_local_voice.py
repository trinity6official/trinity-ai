from voice.local import LocalVoiceService


class FakeTTS:
    name = "fake-tts"
    def __init__(self, available=True): self._available = available; self.calls = []
    def available(self): return self._available
    def speak(self, text, language="english"):
        self.calls.append((text, language)); return True
    def render(self, text, language="english"):
        return b"audio", "fake"


class FakeSTT:
    name = "fake-stt"
    def __init__(self, available=True): self._available = available
    def available(self): return self._available
    def transcribe(self, audio_file):
        return {"text": "hello", "language": "en", "segments": []}


def test_local_voice_speaks_through_provider():
    tts = FakeTTS(); service = LocalVoiceService(tts=tts, stt=FakeSTT())
    assert service.speak("hello", "english") is True
    assert tts.calls == [("hello", "english")]


def test_local_voice_returns_false_without_tts():
    service = LocalVoiceService(tts=FakeTTS(False), stt=FakeSTT())
    assert service.speak("hello") is False


def test_local_voice_listens_through_provider():
    service = LocalVoiceService(tts=FakeTTS(), stt=FakeSTT())
    assert service.listen("audio.wav")["text"] == "hello"


def test_local_voice_returns_none_without_stt():
    service = LocalVoiceService(tts=FakeTTS(), stt=FakeSTT(False))
    assert service.listen("audio.wav") is None


def test_local_voice_can_render_bytes_for_api():
    service = LocalVoiceService(tts=FakeTTS(), stt=FakeSTT())
    assert service.render("hello") == (b"audio", "fake")
