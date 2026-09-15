"""Continuous local microphone runtime for Trinity voice sessions."""
from __future__ import annotations

from threading import Event, Thread
from typing import Any

from voice.capture import MicrophoneCaptureProvider
from voice.session import VoiceSessionController, VoiceTurn


class LocalVoiceRuntime:
    """Feed ephemeral microphone captures into a VoiceSessionController."""

    def __init__(
        self,
        session: VoiceSessionController,
        capture: MicrophoneCaptureProvider,
        *,
        chunk_seconds: float = 5.0,
        event_bus: Any = None,
        error_backoff_seconds: float = 1.0,
    ) -> None:
        self.session = session
        self.capture = capture
        self.chunk_seconds = max(0.5, float(chunk_seconds))
        self.events = event_bus
        self.error_backoff_seconds = max(0.05, float(error_backoff_seconds))
        self._stop = Event()
        self._thread: Thread | None = None
        self.error: str | None = None

    def available(self) -> bool:
        return bool(self.capture.available() and self.session.voice.can_listen())

    def process_once(self) -> VoiceTurn:
        captured = self.capture.capture(self.chunk_seconds)
        try:
            return self.session.process_audio(captured.path)
        finally:
            captured.cleanup()

    def _run(self) -> None:
        if self.events is not None:
            self.events.publish("voice.runtime_started")
        try:
            while not self._stop.is_set():
                try:
                    turn = self.process_once()
                    if turn.error:
                        self.error = turn.error
                        if self.events is not None:
                            self.events.publish("voice.runtime_error", error=turn.error)
                    else:
                        self.error = None
                except Exception as exc:
                    # Continuous voice is an always-on service. A transient microphone,
                    # decoder or STT failure must not permanently kill the listener.
                    self.error = str(exc)
                    if self.events is not None:
                        self.events.publish("voice.runtime_error", error=self.error)
                    if self._stop.wait(self.error_backoff_seconds):
                        break
        finally:
            if self.events is not None:
                self.events.publish("voice.runtime_stopped")

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return True
        if not self.available():
            self.error = "Local microphone/STT is unavailable"
            return False
        self.error = None
        self._stop.clear()
        self._thread = Thread(target=self._run, name="trinity-voice", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        self.session.interrupt()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=self.chunk_seconds + 2)
