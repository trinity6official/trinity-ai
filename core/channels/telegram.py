"""Telegram transport for Trinity.

The transport owns Telegram HTTP details so the main Trinity orchestrator does not
need to know endpoint URLs, polling parameters, or message chunking rules.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests


ErrorHandler = Callable[[Exception], None]


class TelegramChannel:
    """Small adapter around Telegram's Bot API."""

    MAX_MESSAGE_CHARS = 4000

    def __init__(
        self,
        token: str | None,
        chat_id: str | None,
        *,
        error_handler: ErrorHandler | None = None,
        session: Any = requests,
        enabled: bool = True,
        remote_notifications: bool = False,
    ) -> None:
        self.token = token
        self.chat_id = chat_id
        self.error_handler = error_handler
        self.session = session
        self.enabled = enabled
        self.remote_notifications = remote_notifications

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.token and self.chat_id)

    def _endpoint(self, method: str) -> str:
        if not self.token:
            raise RuntimeError("Telegram bot token is not configured")
        return f"https://api.telegram.org/bot{self.token}/{method}"

    def _report_error(self, exc: Exception) -> None:
        if self.error_handler is not None:
            self.error_handler(exc)

    def send(self, message: str) -> bool:
        """Send a message, splitting long text into Telegram-safe chunks."""
        if not self.configured:
            return False

        chunks = [
            message[i : i + self.MAX_MESSAGE_CHARS]
            for i in range(0, len(message), self.MAX_MESSAGE_CHARS)
        ] or [""]

        try:
            for chunk in chunks:
                self.session.post(
                    self._endpoint("sendMessage"),
                    json={"chat_id": self.chat_id, "text": chunk},
                    timeout=10,
                )
            return True
        except Exception as exc:  # transport boundary: keep the caller alive
            self._report_error(exc)
            return False

    def get_updates(self, offset: int | None = None) -> dict[str, Any]:
        """Long-poll Telegram for new message updates."""
        if not self.configured:
            return {"ok": False, "result": []}

        params: dict[str, Any] = {
            "timeout": 30,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            params["offset"] = offset

        try:
            response = self.session.get(
                self._endpoint("getUpdates"), params=params, timeout=35
            )
            return response.json()
        except Exception as exc:
            self._report_error(exc)
            return {"ok": False, "result": []}


    def download_file(self, file_id: str) -> tuple[str, bytes]:
        """Resolve and download a Telegram file for optional remote attachments."""
        if not self.configured:
            raise RuntimeError("Telegram remote chat is not configured")
        try:
            file_response = self.session.get(
                self._endpoint("getFile"),
                params={"file_id": file_id},
                timeout=10,
            )
            file_info = file_response.json()
            if not file_info.get("ok"):
                raise RuntimeError("Telegram could not resolve the uploaded file")
            file_path = file_info["result"]["file_path"]
            raw_response = self.session.get(
                f"https://api.telegram.org/file/bot{self.token}/{file_path}",
                timeout=30,
            )
            return file_path, raw_response.content
        except Exception as exc:
            self._report_error(exc)
            raise

    def latest_offset(self) -> int | None:
        """Return an offset that skips all updates already queued at startup."""
        if not self.configured:
            return None
        try:
            response = self.session.get(self._endpoint("getUpdates"), timeout=10)
            updates = response.json().get("result", [])
            if updates:
                return int(updates[-1]["update_id"]) + 1
            return None
        except Exception as exc:
            self._report_error(exc)
            return None
