from pathlib import Path

from core.events import EventBus
from voice.capture import CapturedAudio
from voice.runtime import LocalVoiceRuntime
from voice.session import VoiceTurn


class FakeLocalVoice:
    def can_listen(self):
        return True


class FakeSession:
    def __init__(self):
        self.voice = FakeLocalVoice()
        self.paths = []
        self.interrupts = 0

    def process_audio(self, path):
        self.paths.append(path)
        return VoiceTurn(transcript="hello", response="hi", spoken=True)

    def interrupt(self):
        self.interrupts += 1


class FakeCapture:
    def __init__(self, path, available=True):
        self.path = str(path)
        self._available = available
        self.calls = 0

    def available(self):
        return self._available

    def capture(self, duration_seconds=5.0):
        self.calls += 1
        Path(self.path).write_bytes(b"audio")
        return CapturedAudio(self.path)


def test_voice_runtime_processes_and_deletes_ephemeral_capture(tmp_path):
    path = tmp_path / "capture.wav"
    session = FakeSession(); capture = FakeCapture(path)
    runtime = LocalVoiceRuntime(session, capture)
    turn = runtime.process_once()
    assert turn.response == "hi"
    assert session.paths == [str(path)]
    assert not path.exists()


def test_voice_runtime_refuses_to_start_without_capture(tmp_path):
    runtime = LocalVoiceRuntime(FakeSession(), FakeCapture(tmp_path / "x.wav", available=False))
    assert runtime.start() is False
    assert "unavailable" in runtime.error.lower()


def test_voice_runtime_emits_lifecycle_events(tmp_path):
    class OneShotRuntime(LocalVoiceRuntime):
        def process_once(self):
            self._stop.set()
            return VoiceTurn()

    bus = EventBus(); seen=[]; bus.subscribe("*", lambda event: seen.append(event.type))
    runtime = OneShotRuntime(FakeSession(), FakeCapture(tmp_path / "x.wav"), event_bus=bus)
    assert runtime.start() is True
    runtime._thread.join(timeout=2)
    assert "voice.runtime_started" in seen
    assert "voice.runtime_stopped" in seen


def test_voice_runtime_recovers_from_transient_turn_failure(tmp_path):
    class FlakyRuntime(LocalVoiceRuntime):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = 0

        def process_once(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary microphone failure")
            self._stop.set()
            return VoiceTurn(response="recovered")

    bus = EventBus(); seen = []
    bus.subscribe("*", lambda event: seen.append((event.type, event.payload)))
    runtime = FlakyRuntime(
        FakeSession(),
        FakeCapture(tmp_path / "x.wav"),
        event_bus=bus,
        error_backoff_seconds=0.01,
    )
    assert runtime.start() is True
    runtime._thread.join(timeout=2)
    assert runtime.calls == 2
    assert runtime.error is None
    assert any(kind == "voice.runtime_error" for kind, _ in seen)
    assert seen[-1][0] == "voice.runtime_stopped"
