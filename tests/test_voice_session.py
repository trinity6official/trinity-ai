from voice.session import VoiceSessionController, VoiceState


class FakeVoice:
    def __init__(self, text="hello", language="en"):
        self.text = text
        self.language = language
        self.spoken = []
        self.stopped = 0

    def listen(self, path):
        return {"text": self.text, "language": self.language}

    def speak(self, text, language="english"):
        self.spoken.append((text, language))
        return True

    def stop_speaking(self):
        self.stopped += 1


def test_voice_turn_runs_stt_reasoning_tts_and_returns_idle():
    voice = FakeVoice()
    states = []
    session = VoiceSessionController(
        voice, lambda text, lang: f"reply:{text}", on_state_change=states.append
    )
    turn = session.process_audio("a.wav")
    assert turn.transcript == "hello"
    assert turn.response == "reply:hello"
    assert turn.spoken is True
    assert voice.spoken == [("reply:hello", "en")]
    assert states == [VoiceState.LISTENING, VoiceState.THINKING, VoiceState.SPEAKING, VoiceState.IDLE]


def test_wake_word_gate_ignores_until_trinity_is_heard():
    voice = FakeVoice("weather please")
    calls = []
    session = VoiceSessionController(
        voice, lambda text, lang: calls.append(text) or "reply", require_wake_word=True
    )
    ignored = session.process_audio("a.wav")
    assert ignored.ignored is True
    assert calls == []

    voice.text = "Trinity, weather please"
    turn = session.process_audio("b.wav")
    assert turn.transcript == "weather please"
    assert calls == ["weather please"]


def test_interrupt_stops_current_tts_provider():
    voice = FakeVoice()
    session = VoiceSessionController(voice, lambda text, lang: "reply")
    session.interrupt()
    assert voice.stopped == 1
    assert session.state == VoiceState.INTERRUPTED


def test_stt_unavailable_fails_without_calling_responder():
    class NoSTT(FakeVoice):
        def listen(self, path): return None
    calls=[]
    session = VoiceSessionController(NoSTT(), lambda text, lang: calls.append(text) or "reply")
    turn = session.process_audio("a.wav")
    assert turn.error
    assert calls == []
