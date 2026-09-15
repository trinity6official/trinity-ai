"""Android/Termux speech adapters for Trinity's pre-hardware test profile.

These adapters intentionally use Termux:API commands instead of embedding an
Android SDK dependency into Trinity's core runtime.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


class TermuxTTS:
    name = "termux-tts"

    def available(self) -> bool:
        return shutil.which("termux-tts-speak") is not None

    def speak(self, text: str, language: str = "english") -> bool:
        if not self.available():
            return False
        result = subprocess.run(
            ["termux-tts-speak", text],
            check=False,
            timeout=120,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def stop(self) -> None:
        # Termux:API does not currently expose a reliable generic TTS stop
        # command.  Keep the method for VoiceSessionController compatibility.
        return None


class TermuxSpeechToText:
    name = "termux-speech-to-text"

    def available(self) -> bool:
        return shutil.which("termux-speech-to-text") is not None

    def transcribe(self, audio_file: str = "") -> dict[str, Any]:
        """Capture one spoken utterance through Android's speech recognizer.

        ``audio_file`` is accepted for the common STT protocol but ignored: the
        Termux command itself owns microphone capture for this test profile.
        """
        if not self.available():
            raise RuntimeError(
                "termux-speech-to-text is unavailable. Install the Termux:API "
                "app and run `pkg install termux-api`."
            )
        result = subprocess.run(
            ["termux-speech-to-text"],
            check=False,
            timeout=120,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown error").strip()
            raise RuntimeError(f"Android speech recognition failed: {detail}")
        raw = result.stdout.strip()
        text = raw
        # Some Termux:API versions return JSON-shaped output. Accept both forms.
        if raw.startswith("{"):
            try:
                payload = json.loads(raw)
                text = str(payload.get("text") or payload.get("result") or raw)
            except json.JSONDecodeError:
                text = raw
        return {"text": text.strip(), "language": None, "segments": []}
