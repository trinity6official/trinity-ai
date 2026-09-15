"""Local conversational voice-session orchestration for Trinity."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Event
from typing import Callable

from voice.local import LocalVoiceService


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass(frozen=True)
class VoiceTurn:
    transcript: str = ""
    response: str = ""
    language: str | None = None
    spoken: bool = False
    ignored: bool = False
    error: str | None = None


StateCallback = Callable[[VoiceState], None]
Responder = Callable[[str, str], str]


class VoiceSessionController:
    """Coordinate local STT → Trinity → local TTS with interruption support.

    Audio capture itself remains pluggable. This controller consumes a local
    audio file so microphone/wake-word implementations can evolve independently.
    """

    def __init__(
        self,
        voice: LocalVoiceService,
        responder: Responder,
        *,
        on_state_change: StateCallback | None = None,
        wake_words: tuple[str, ...] = ("trinity",),
        require_wake_word: bool = False,
    ) -> None:
        self.voice = voice
        self.responder = responder
        self.on_state_change = on_state_change
        self.wake_words = tuple(word.lower().strip() for word in wake_words if word.strip())
        self.require_wake_word = require_wake_word
        self.state = VoiceState.IDLE
        self.active = not require_wake_word
        self._interrupted = Event()

    def _set_state(self, state: VoiceState) -> None:
        self.state = state
        if self.on_state_change is not None:
            self.on_state_change(state)

    def activate(self) -> None:
        self.active = True
        self._interrupted.clear()
        self._set_state(VoiceState.IDLE)

    def deactivate(self) -> None:
        self.interrupt()
        self.active = False
        self._set_state(VoiceState.IDLE)

    def interrupt(self) -> None:
        """Stop current speech and mark the turn as interrupted (barge-in)."""
        self._interrupted.set()
        stop = getattr(self.voice, "stop_speaking", None)
        if callable(stop):
            stop()
        self._set_state(VoiceState.INTERRUPTED)

    def _wake_gate(self, transcript: str) -> tuple[bool, str]:
        text = transcript.strip()
        if self.active or not self.require_wake_word:
            return True, text
        lower = text.lower()
        for word in self.wake_words:
            index = lower.find(word)
            if index >= 0:
                self.active = True
                before = text[:index]
                after = text[index + len(word):]
                cleaned = (before + " " + after).strip(" ,.:;-\t")
                return True, cleaned
        return False, text

    def process_audio(self, audio_file: str, language: str = "english") -> VoiceTurn:
        self._interrupted.clear()
        try:
            self._set_state(VoiceState.LISTENING)
            transcription = self.voice.listen(audio_file)
            if not transcription:
                self._set_state(VoiceState.IDLE)
                return VoiceTurn(error="Local speech recognition is unavailable")

            transcript = str(transcription.get("text", "")).strip()
            detected_language = transcription.get("language") or language
            allowed, prompt = self._wake_gate(transcript)
            if not allowed:
                self._set_state(VoiceState.IDLE)
                return VoiceTurn(
                    transcript=transcript,
                    language=str(detected_language),
                    ignored=True,
                )
            if not prompt:
                self._set_state(VoiceState.IDLE)
                return VoiceTurn(transcript=transcript, language=str(detected_language), ignored=True)

            if self._interrupted.is_set():
                return VoiceTurn(transcript=prompt, language=str(detected_language), ignored=True)

            self._set_state(VoiceState.THINKING)
            response = str(self.responder(prompt, str(detected_language)))
            if self._interrupted.is_set():
                return VoiceTurn(
                    transcript=prompt, response=response,
                    language=str(detected_language), ignored=True,
                )

            self._set_state(VoiceState.SPEAKING)
            spoken = bool(self.voice.speak(response, str(detected_language)))
            if self._interrupted.is_set():
                return VoiceTurn(
                    transcript=prompt, response=response,
                    language=str(detected_language), spoken=False, ignored=True,
                )

            self._set_state(VoiceState.IDLE)
            return VoiceTurn(
                transcript=prompt,
                response=response,
                language=str(detected_language),
                spoken=spoken,
            )
        except Exception as exc:
            self._set_state(VoiceState.ERROR)
            return VoiceTurn(error=str(exc))
