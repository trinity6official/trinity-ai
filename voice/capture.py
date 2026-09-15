"""Local microphone capture providers for Trinity.

Capture is intentionally separate from STT. The default macOS implementation
uses a locally installed ffmpeg/AVFoundation process and writes a short-lived
WAV file that is deleted immediately after the voice turn is processed.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class CapturedAudio:
    path: str
    temporary: bool = True

    def cleanup(self) -> None:
        if self.temporary:
            Path(self.path).unlink(missing_ok=True)


class MicrophoneCaptureProvider(Protocol):
    name: str

    def available(self) -> bool: ...
    def capture(self, duration_seconds: float = 5.0) -> CapturedAudio: ...


class FfmpegMicrophoneCapture:
    """Capture local macOS microphone audio through ffmpeg AVFoundation."""

    name = "ffmpeg-avfoundation"

    def __init__(
        self,
        *,
        binary: str | None = None,
        input_spec: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> None:
        self.binary = binary or shutil.which("ffmpeg") or "ffmpeg"
        self.input_spec = input_spec or os.environ.get("TRINITY_MIC_INPUT", ":0")
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)

    def available(self) -> bool:
        return platform.system() == "Darwin" and shutil.which(self.binary) is not None

    def capture(self, duration_seconds: float = 5.0) -> CapturedAudio:
        if not self.available():
            raise RuntimeError("Local microphone capture requires ffmpeg on macOS")
        duration = max(0.5, float(duration_seconds))
        fd, path = tempfile.mkstemp(prefix="trinity-mic-", suffix=".wav")
        os.close(fd)
        try:
            subprocess.run(
                [
                    self.binary,
                    "-hide_banner",
                    "-loglevel", "error",
                    "-f", "avfoundation",
                    "-i", self.input_spec,
                    "-t", str(duration),
                    "-ac", str(self.channels),
                    "-ar", str(self.sample_rate),
                    "-y", path,
                ],
                check=True,
                timeout=duration + 10,
            )
            return CapturedAudio(path)
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
