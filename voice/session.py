"""Local conversational voice-session orchestration for Trinity."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Event
from typing import Callable

from core.trust_context import TrustContext, use_trust_context
from voice.identity import (
    SpeakerVerification,
    SpeakerVerificationStatus,
    SpeakerVerifier,
    trust_context_for_voice,
)
from voice.local import LocalVoiceService
from voice.wake_session import WakeSessionManager


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    VERIFYING = "verifying"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptUpdate:
    """A partial or final text side-channel from any speech front end."""

    text: str
    language: str
    final: bool
    confidence: float | None = None


@dataclass(frozen=True)
class VoiceTurn:
    transcript: str = ""
    response: str = ""
    language: str | None = None
    spoken: bool = False
    ignored: bool = False
    interrupted: bool = False
    trust_level: str | None = None
    speaker_verified: bool | None = None
    error: str | None = None


StateCallback = Callable[[VoiceState], None]
TranscriptCallback = Callable[[TranscriptUpdate, TrustContext], None]
Responder = Callable[[str, str], str]


class VoiceSessionController:
    """Coordinate speech input → Trinity → speech output.

    The current local STT/TTS path remains supported through ``process_audio``.
    Native/streaming speech front ends can feed partial and final transcripts
    through ``ingest_transcript`` without bypassing Trinity's text, memory,
    permission or audit layers.

    When wake-word mode is enabled, speaker identity is checked once when a
    session opens and cached until the wake session expires from inactivity.
    """

    def __init__(
        self,
        voice: LocalVoiceService,
        responder: Responder,
        *,
        on_state_change: StateCallback | None = None,
        on_transcript: TranscriptCallback | None = None,
        speaker_verifier: SpeakerVerifier | None = None,
        wake_words: tuple[str, ...] = ("trinity",),
        require_wake_word: bool = False,
        wake_session_manager: WakeSessionManager | None = None,
        wake_session_timeout_seconds: float = 300.0,
    ) -> None:
        self.voice = voice
        self.responder = responder
        self.on_state_change = on_state_change
        self.on_transcript = on_transcript
        self.speaker_verifier = speaker_verifier
        self.wake_words = tuple(word.lower().strip() for word in wake_words if word.strip())
        self.require_wake_word = require_wake_word
        self.wake_session = wake_session_manager or WakeSessionManager(
            wake_session_timeout_seconds
        )
        self.state = VoiceState.IDLE
        self.active = not require_wake_word
        self._interrupted = Event()

    def _set_state(self, state: VoiceState) -> None:
        self.state = state
        if self.on_state_change is not None:
            self.on_state_change(state)

    def activate(self) -> None:
        self.active = True
        if self.require_wake_word and not self.wake_session.active:
            self.wake_session.open()
        self._interrupted.clear()
        self._set_state(VoiceState.IDLE)

    def deactivate(self) -> None:
        self.interrupt()
        self.end_wake_session()
        self._set_state(VoiceState.IDLE)

    def end_wake_session(self) -> None:
        """Expire cached speaker trust immediately."""
        self.wake_session.close()
        self.active = not self.require_wake_word

    def wake_session_status(self) -> dict[str, object]:
        """Return lightweight session state for diagnostics/UI."""
        status = self.wake_session.status()
        if self.require_wake_word and not status["active"]:
            self.active = False
        return status

    def interrupt(self) -> None:
        """Stop current speech and mark the turn as interrupted (barge-in)."""
        self._interrupted.set()
        stop = getattr(self.voice, "stop_speaking", None)
        if callable(stop):
            stop()
        self._set_state(VoiceState.INTERRUPTED)

    def _wake_gate(self, transcript: str) -> tuple[bool, str, bool]:
        text = transcript.strip()
        if not self.require_wake_word:
            return True, text, False

        if self.wake_session.active:
            self.active = True
            return True, text, False

        # A previously active session may have expired since the last turn.
        self.active = False
        lower = text.lower()
        for word in self.wake_words:
            index = lower.find(word)
            if index >= 0:
                before = text[:index]
                after = text[index + len(word):]
                cleaned = (before + " " + after).strip(" ,.:;-\t")
                return True, cleaned, True
        return False, text, False

    @staticmethod
    def _speaker_flag(
        verification: SpeakerVerification | None,
        context: TrustContext,
    ) -> bool | None:
        if verification is not None:
            return verification.owner_verified
        if context.source.value == "local_voice" and context.owner_verified:
            return True
        return None

    def _notify_transcript(
        self,
        update: TranscriptUpdate,
        context: TrustContext,
    ) -> None:
        if self.on_transcript is not None:
            self.on_transcript(update, context)

    def _cached_context(
        self,
        fallback_context: TrustContext,
        fallback_verification: SpeakerVerification | None,
    ) -> tuple[TrustContext, SpeakerVerification | None]:
        if not self.require_wake_word:
            return fallback_context, fallback_verification
        session = self.wake_session.current
        if session is None:
            return fallback_context, fallback_verification
        return session.trust_context, session.verification

    def ingest_transcript(
        self,
        text: str,
        language: str = "english",
        *,
        final: bool,
        confidence: float | None = None,
        trust_context: TrustContext | None = None,
        speaker_verification: SpeakerVerification | None = None,
    ) -> VoiceTurn | None:
        """Accept streaming transcript updates from any speech provider.

        Partial text is surfaced only through ``on_transcript``. A final
        transcript enters the normal Trinity reasoning/TTS path.
        """
        context = trust_context or trust_context_for_voice(speaker_verification)
        context, speaker_verification = self._cached_context(
            context, speaker_verification
        )
        update = TranscriptUpdate(
            text=str(text or "").strip(),
            language=str(language or "english"),
            final=bool(final),
            confidence=confidence,
        )
        self._notify_transcript(update, context)

        if not final:
            self._set_state(VoiceState.LISTENING)
            return None

        return self._process_final_transcript(
            update.text,
            update.language,
            context=context,
            speaker_verification=speaker_verification,
        )

    def process_transcript(
        self,
        text: str,
        language: str = "english",
        *,
        trust_context: TrustContext | None = None,
        speaker_verification: SpeakerVerification | None = None,
        confidence: float | None = None,
    ) -> VoiceTurn:
        """Process a finalized transcript without requiring batch STT."""
        turn = self.ingest_transcript(
            text,
            language,
            final=True,
            confidence=confidence,
            trust_context=trust_context,
            speaker_verification=speaker_verification,
        )
        assert turn is not None
        return turn

    def _process_final_transcript(
        self,
        transcript: str,
        language: str,
        *,
        context: TrustContext,
        speaker_verification: SpeakerVerification | None,
    ) -> VoiceTurn:
        allowed, prompt, opened_by_wake = self._wake_gate(transcript)
        if not allowed:
            self._set_state(VoiceState.IDLE)
            return VoiceTurn(
                transcript=transcript,
                language=language,
                trust_level=context.level.value,
                speaker_verified=self._speaker_flag(speaker_verification, context),
                ignored=True,
            )

        if self.require_wake_word:
            if opened_by_wake:
                wake_session = self.wake_session.open(
                    verification=speaker_verification,
                    trust_context=context,
                )
                self.active = True
                context = wake_session.trust_context
                speaker_verification = wake_session.verification
            else:
                wake_session = self.wake_session.touch()
                if wake_session is not None:
                    context = wake_session.trust_context
                    speaker_verification = wake_session.verification

        speaker_verified = self._speaker_flag(speaker_verification, context)
        common = {
            "language": language,
            "trust_level": context.level.value,
            "speaker_verified": speaker_verified,
        }

        # Saying only the wake word opens the session without invoking the LLM.
        if not prompt:
            self._set_state(VoiceState.IDLE)
            return VoiceTurn(transcript=transcript, ignored=True, **common)

        if self._interrupted.is_set():
            return VoiceTurn(
                transcript=prompt,
                ignored=True,
                interrupted=True,
                **common,
            )

        self._set_state(VoiceState.THINKING)
        with use_trust_context(context):
            response = str(self.responder(prompt, language))
        if self._interrupted.is_set():
            return VoiceTurn(
                transcript=prompt,
                response=response,
                ignored=True,
                interrupted=True,
                **common,
            )

        self._set_state(VoiceState.SPEAKING)
        spoken = bool(self.voice.speak(response, language))
        if self._interrupted.is_set():
            return VoiceTurn(
                transcript=prompt,
                response=response,
                spoken=False,
                ignored=True,
                interrupted=True,
                **common,
            )

        if self.require_wake_word:
            self.wake_session.touch()
        self._set_state(VoiceState.IDLE)
        return VoiceTurn(
            transcript=prompt,
            response=response,
            spoken=spoken,
            **common,
        )

    def _verify_speaker(self, audio_file: str) -> SpeakerVerification | None:
        if self.speaker_verifier is None:
            return None
        self._set_state(VoiceState.VERIFYING)
        try:
            return self.speaker_verifier.verify(audio_file)
        except Exception as exc:
            # Identity provider failure must fail closed, but it should not make
            # the entire conversational voice service unavailable.
            return SpeakerVerification(
                SpeakerVerificationStatus.UNKNOWN,
                reason=f"speaker verification failed: {exc}",
            )

    def process_audio(self, audio_file: str, language: str = "english") -> VoiceTurn:
        self._interrupted.clear()
        try:
            self._set_state(VoiceState.LISTENING)
            transcription = self.voice.listen(audio_file)
            if not transcription:
                self._set_state(VoiceState.IDLE)
                return VoiceTurn(error="Local speech recognition is unavailable")

            transcript = str(transcription.get("text", "")).strip()
            detected_language = str(transcription.get("language") or language)
            confidence = transcription.get("confidence")

            verification: SpeakerVerification | None = None
            context: TrustContext | None = None

            if self.require_wake_word:
                session = self.wake_session.current
                if session is not None:
                    # Fast path: reuse cached identity/trust for the active session.
                    context = session.trust_context
                    verification = session.verification
                else:
                    allowed, _prompt, opened_by_wake = self._wake_gate(transcript)
                    if not allowed or not opened_by_wake:
                        # Crucially, do not run speaker verification for ambient
                        # audio that did not contain the wake word.
                        return self.process_transcript(
                            transcript,
                            detected_language,
                            confidence=confidence,
                        )
                    verification = self._verify_speaker(audio_file)
                    context = trust_context_for_voice(verification)
            else:
                # Compatibility path for push-to-talk/non-wake-word callers.
                verification = self._verify_speaker(audio_file)
                context = trust_context_for_voice(verification)

            return self.process_transcript(
                transcript,
                detected_language,
                trust_context=context,
                speaker_verification=verification,
                confidence=confidence,
            )
        except Exception as exc:
            self._set_state(VoiceState.ERROR)
            return VoiceTurn(error=str(exc))
