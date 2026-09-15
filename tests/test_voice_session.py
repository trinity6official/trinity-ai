from core.trust_context import (
    RequestSource,
    TrustContext,
    TrustLevel,
    get_current_trust_context,
)
from voice.identity import SpeakerVerification, SpeakerVerificationStatus
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


class FakeVerifier:
    def __init__(self, result):
        self.result = result
        self.paths = []

    def verify(self, audio_file):
        self.paths.append(audio_file)
        return self.result


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
    assert turn.trust_level == "unverified"
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


def test_unverified_ambient_voice_reaches_responder_as_unverified():
    seen = []

    def responder(text, language):
        seen.append(get_current_trust_context().level)
        return "reply"

    turn = VoiceSessionController(FakeVoice(), responder).process_audio("ambient.wav")
    assert seen == [TrustLevel.UNVERIFIED]
    assert turn.speaker_verified is None


def test_verified_speaker_reaches_responder_as_trusted():
    seen = []
    verifier = FakeVerifier(
        SpeakerVerification(
            SpeakerVerificationStatus.VERIFIED,
            speaker_id="david",
            confidence=0.98,
        )
    )

    def responder(text, language):
        seen.append(get_current_trust_context().level)
        return "reply"

    turn = VoiceSessionController(
        FakeVoice(),
        responder,
        speaker_verifier=verifier,
    ).process_audio("david.wav")

    assert verifier.paths == ["david.wav"]
    assert seen == [TrustLevel.TRUSTED]
    assert turn.trust_level == "trusted"
    assert turn.speaker_verified is True


def test_partial_transcript_is_side_channel_only_until_final():
    calls = []
    updates = []
    context = TrustContext.local_trusted(
        source=RequestSource.LOCAL_VOICE,
        subject="david",
    )
    session = VoiceSessionController(
        FakeVoice(),
        lambda text, lang: calls.append(text) or "reply",
        on_transcript=lambda update, trust: updates.append((update, trust)),
    )

    assert session.ingest_transcript(
        "hello tri",
        "en",
        final=False,
        trust_context=context,
    ) is None
    assert calls == []
    assert updates[-1][0].final is False
    assert updates[-1][1].level == TrustLevel.TRUSTED

    turn = session.ingest_transcript(
        "hello trinity",
        "en",
        final=True,
        trust_context=context,
    )
    assert turn is not None
    assert calls == ["hello trinity"]
    assert turn.response == "reply"


def test_final_transcript_entry_point_supports_future_native_speech_frontend():
    context = TrustContext.local_trusted(
        source=RequestSource.LOCAL_VOICE,
        subject="david",
    )
    seen = []

    def responder(text, language):
        seen.append((text, language, get_current_trust_context().level))
        return "native reply"

    turn = VoiceSessionController(FakeVoice(), responder).process_transcript(
        "what is my schedule",
        "en",
        trust_context=context,
    )
    assert seen == [("what is my schedule", "en", TrustLevel.TRUSTED)]
    assert turn.response == "native reply"
    assert turn.trust_level == "trusted"


def test_speaker_verifier_failure_fails_closed_without_breaking_voice():
    class BrokenVerifier:
        def verify(self, audio_file):
            raise RuntimeError("model unavailable")

    seen = []

    def responder(text, language):
        seen.append(get_current_trust_context().level)
        return "reply"

    turn = VoiceSessionController(
        FakeVoice(),
        responder,
        speaker_verifier=BrokenVerifier(),
    ).process_audio("a.wav")
    assert turn.error is None
    assert turn.trust_level == "unverified"
    assert turn.speaker_verified is None
    assert seen == [TrustLevel.UNVERIFIED]
