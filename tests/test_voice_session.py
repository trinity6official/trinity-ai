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


def test_wake_mode_does_not_verify_ambient_audio_before_wake_word():
    verifier = FakeVerifier(
        SpeakerVerification(
            SpeakerVerificationStatus.VERIFIED,
            speaker_id="david",
            confidence=0.99,
        )
    )
    voice = FakeVoice("background conversation")
    session = VoiceSessionController(
        voice,
        lambda text, lang: "reply",
        speaker_verifier=verifier,
        require_wake_word=True,
    )

    turn = session.process_audio("ambient.wav")
    assert turn.ignored is True
    assert verifier.paths == []


def test_speaker_is_verified_once_then_reused_for_wake_session():
    verifier = FakeVerifier(
        SpeakerVerification(
            SpeakerVerificationStatus.VERIFIED,
            speaker_id="david",
            confidence=0.99,
        )
    )
    voice = FakeVoice("Trinity, what is the weather")
    seen = []

    def responder(text, language):
        seen.append((text, get_current_trust_context().level))
        return "reply"

    session = VoiceSessionController(
        voice,
        responder,
        speaker_verifier=verifier,
        require_wake_word=True,
    )

    first = session.process_audio("wake.wav")
    assert first.trust_level == "trusted"
    assert verifier.paths == ["wake.wav"]

    voice.text = "and tomorrow"
    second = session.process_audio("followup.wav")
    assert second.trust_level == "trusted"
    assert verifier.paths == ["wake.wav"]
    assert seen == [
        ("what is the weather", TrustLevel.TRUSTED),
        ("and tomorrow", TrustLevel.TRUSTED),
    ]


def test_saying_only_wake_word_opens_session_without_llm_call():
    calls = []
    voice = FakeVoice("Trinity")
    session = VoiceSessionController(
        voice,
        lambda text, lang: calls.append(text) or "reply",
        require_wake_word=True,
    )

    turn = session.process_audio("wake.wav")
    assert turn.ignored is True
    assert calls == []
    assert session.wake_session_status()["active"] is True


def test_expired_session_requires_wake_word_and_reverification():
    from voice.wake_session import WakeSessionManager

    class FakeClock:
        def __init__(self):
            self.now = 0.0
        def __call__(self):
            return self.now
        def advance(self, seconds):
            self.now += seconds

    clock = FakeClock()
    manager = WakeSessionManager(5, clock=clock)
    verifier = FakeVerifier(
        SpeakerVerification(
            SpeakerVerificationStatus.VERIFIED,
            speaker_id="david",
            confidence=0.99,
        )
    )
    voice = FakeVoice("Trinity, status")
    calls = []
    session = VoiceSessionController(
        voice,
        lambda text, lang: calls.append(text) or "reply",
        speaker_verifier=verifier,
        require_wake_word=True,
        wake_session_manager=manager,
    )

    session.process_audio("wake1.wav")
    assert verifier.paths == ["wake1.wav"]

    clock.advance(6)
    voice.text = "status again"
    expired = session.process_audio("no-wake.wav")
    assert expired.ignored is True
    assert verifier.paths == ["wake1.wav"]

    voice.text = "Trinity, status again"
    session.process_audio("wake2.wav")
    assert verifier.paths == ["wake1.wav", "wake2.wav"]


def test_explicit_end_wake_session_drops_cached_identity():
    verifier = FakeVerifier(
        SpeakerVerification(
            SpeakerVerificationStatus.VERIFIED,
            speaker_id="david",
            confidence=0.99,
        )
    )
    voice = FakeVoice("Trinity, hello")
    session = VoiceSessionController(
        voice,
        lambda text, lang: "reply",
        speaker_verifier=verifier,
        require_wake_word=True,
    )
    session.process_audio("wake.wav")
    assert session.wake_session_status()["active"] is True

    session.end_wake_session()
    assert session.wake_session_status()["active"] is False
