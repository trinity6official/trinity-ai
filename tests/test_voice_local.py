from voice.speak import TrinityVoice


class FakeLocalVoice:
    def __init__(self, can_speak=True):
        self._can_speak = can_speak
        self.spoken = []

    def can_speak(self):
        return self._can_speak

    def speak(self, text, language="english"):
        self.spoken.append((text, language))
        return self._can_speak

    def listen(self, audio_file):
        return {"text": "hello", "language": "en"}

    def render(self, text, language="english"):
        return b"audio", "aiff"


def test_voice_is_local_only_and_does_not_need_telegram():
    provider = FakeLocalVoice()
    voice = TrinityVoice(telegram_token="ignored", chat_id="ignored", local_voice=provider)
    assert voice.speak("hello") is True
    assert provider.spoken == [("hello", "english")]


def test_voice_listen_and_render_use_local_provider():
    voice = TrinityVoice(local_voice=FakeLocalVoice())
    assert voice.listen("sample.wav")["text"] == "hello"
    assert voice.render("hello") == (b"audio", "aiff")


def test_voice_failure_is_text_only_not_remote_fallback():
    voice = TrinityVoice(local_voice=FakeLocalVoice(can_speak=False))
    assert voice.speak("hello") is False
