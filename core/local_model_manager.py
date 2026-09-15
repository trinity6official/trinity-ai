"""Lifecycle management for Trinity's Android llama.cpp server."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalModelManager:
    """Start and stop the llama.cpp instance owned by Trinity."""

    def __init__(
        self,
        root: Path,
        base_url: str = "http://127.0.0.1:8080",
        startup_timeout: int = 180,
    ) -> None:
        self.root = root
        self.base_url = base_url.rstrip("/")
        self.startup_timeout = startup_timeout

        self.script = self.root / "scripts" / "start_android_model.sh"
        self.runtime_dir = self.root / "memory" / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.log_path = self.runtime_dir / "llama-server.log"

        self.process: subprocess.Popen | None = None
        self.owned = False
        self.external_server = False
        self._log_handle = None

    def healthy(self) -> bool:
        """Return True when llama.cpp's health endpoint is ready."""
        request = Request(
            f"{self.base_url}/health",
            method="GET",
        )

        try:
            with urlopen(request, timeout=1.5) as response:
                return 200 <= response.status < 300
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

    def _log_tail(self, lines: int = 20) -> str:
        try:
            content = self.log_path.read_text(errors="replace").splitlines()
            return "\n".join(content[-lines:])
        except OSError:
            return ""

    def start(self) -> bool:
        """
        Ensure llama-server is available.

        Returns True if Trinity started the server.
        Returns False when an already-running external server is reused.
        """
        if self.healthy():
            self.external_server = True
            print("[MODEL] Using existing llama-server.")
            return False

        if not self.script.exists():
            raise RuntimeError(
                f"Model launcher not found: {self.script}"
            )

        if not os.access(self.script, os.X_OK):
            raise RuntimeError(
                f"Model launcher is not executable: {self.script}"
            )

        self.external_server = False

        self._log_handle = self.log_path.open(
            "a",
            encoding="utf-8",
            buffering=1,
        )

        print("[MODEL] Starting Trinity phone model...")

        self.process = subprocess.Popen(
            [str(self.script)],
            cwd=str(self.root),
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
        )

        self.owned = True

        deadline = time.monotonic() + self.startup_timeout

        while time.monotonic() < deadline:
            if self.healthy():
                print(
                    f"[MODEL] llama-server ready "
                    f"(PID {self.process.pid})."
                )
                return True

            if self.process.poll() is not None:
                code = self.process.returncode
                tail = self._log_tail()

                self._close_log()
                self.owned = False

                message = (
                    f"llama-server exited during startup "
                    f"with code {code}."
                )

                if tail:
                    message += f"\n\nLast server log lines:\n{tail}"

                raise RuntimeError(message)

            time.sleep(0.5)

        self.stop()

        tail = self._log_tail()

        message = (
            f"llama-server did not become ready within "
            f"{self.startup_timeout} seconds."
        )

        if tail:
            message += f"\n\nLast server log lines:\n{tail}"

        raise RuntimeError(message)

    def stop(self) -> None:
        """Stop llama-server only when this Trinity process owns it."""
        if not self.owned:
            self._close_log()
            return

        process = self.process

        if process is not None and process.poll() is None:
            print("[MODEL] Stopping Trinity-owned llama-server...")

            try:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            except ProcessLookupError:
                pass

        self.process = None
        self.owned = False

        self._close_log()

        print("[MODEL] llama-server stopped.")

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None

    def status(self) -> str:
        """Return lifecycle status without making another HTTP request."""
        if self.owned and self.process is not None:
            if self.process.poll() is None:
                return (
                    f"running, Trinity-owned "
                    f"(PID {self.process.pid})"
                )
            return (
                f"Trinity-owned process exited "
                f"(code {self.process.returncode})"
            )

        if self.external_server:
            return "running, externally started"

        return "stopped"
