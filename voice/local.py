"""Provider-neutral local speech services for Trinity."""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class TextToSpeechProvider(Protocol):
    name: str
    def available(self) -> bool: ...
    def speak(self, text: str, language: str = "english") -> bool: ...


class SpeechToTextProvider(Protocol):
    name: str
    def available(self) -> bool: ...
    def transcribe(self, audio_file: str) -> dict[str, Any]: ...


class MacSayTTS:
    """Use macOS built-in `say` for fully local, interruptible speech output."""

    name = "macos-say"

    def __init__(self) -> None:
        self._process = None

    def available(self) -> bool:
        return platform.system() == "Darwin" and shutil.which("say") is not None

    def speak(self, text: str, language: str = "english") -> bool:
        if not self.available():
            return False
        self.stop()
        self._process = subprocess.Popen(["say", text])
        try:
            return self._process.wait(timeout=120) == 0
        finally:
            self._process = None

    def stop(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        self._process = None

    def render(self, text: str, language: str = "english") -> tuple[bytes, str]:
        """Render speech to local AIFF bytes for API/mobile responses."""
        if not self.available():
            raise RuntimeError("macOS say is not available")
        import tempfile
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
                path = tmp.name
            subprocess.run(["say", "-o", path, text], check=True, timeout=120)
            return Path(path).read_bytes(), "aiff"
        finally:
            if path:
                Path(path).unlink(missing_ok=True)


class WhisperLocalSTT:
    """Lazy local Whisper speech recognition provider."""

    name = "whisper-local"

    def __init__(self, model_name: str = "small") -> None:
        self.model_name = model_name
        self._model = None

    def available(self) -> bool:
        try:
            import whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _load(self):
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio_file: str) -> dict[str, Any]:
        path = Path(audio_file)
        if not path.exists():
            raise FileNotFoundError(audio_file)
        if not self.available():
            raise RuntimeError("Local Whisper is not installed")
        result = self._load().transcribe(str(path), language=None)
        return {
            "text": result.get("text", ""),
            "language": result.get("language"),
            "segments": result.get("segments", []),
        }


@dataclass
class LocalVoiceService:
    tts: TextToSpeechProvider | None = None
    stt: SpeechToTextProvider | None = None

    def __post_init__(self) -> None:
        if self.tts is None or self.stt is None:
            import os
            profile = os.environ.get("TRINITY_PLATFORM_PROFILE", "macos").strip().lower()
            if profile in {"android", "android_termux", "termux"}:
                from voice.termux import TermuxSpeechToText, TermuxTTS
                if self.tts is None:
                    self.tts = TermuxTTS()
                if self.stt is None:
                    self.stt = TermuxSpeechToText()
            else:
                if self.tts is None:
                    self.tts = MacSayTTS()
                if self.stt is None:
                    self.stt = WhisperLocalSTT()

    def can_speak(self) -> bool:
        return bool(self.tts and self.tts.available())

    def can_listen(self) -> bool:
        return bool(self.stt and self.stt.available())

    def speak(self, text: str, language: str = "english") -> bool:
        if not self.can_speak():
            return False
        return bool(self.tts.speak(text, language))

    def listen(self, audio_file: str) -> dict[str, Any] | None:
        if not self.can_listen():
            return None
        return self.stt.transcribe(audio_file)

    def stop_speaking(self) -> None:
        if self.tts is not None and hasattr(self.tts, "stop"):
            self.tts.stop()

    def render(self, text: str, language: str = "english") -> tuple[bytes, str] | None:
        if not self.can_speak() or not hasattr(self.tts, "render"):
            return None
        return self.tts.render(text, language)
