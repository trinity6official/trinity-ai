"""In-process HTTP API server for Trinity's local daemon."""
from __future__ import annotations

import os
from threading import Thread
from typing import Any

from core.api_security import DEFAULT_JWT_SECRET, validate_api_exposure


class LocalAPIServer:
    """Run FastAPI/uvicorn inside the same process as the Trinity daemon."""

    def __init__(
        self,
        runtime: Any,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.runtime = runtime
        self.host = host or os.environ.get("TRINITY_API_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("TRINITY_API_PORT", "8000"))
        self.server = None
        self.thread: Thread | None = None
        self.error: str | None = None

    @staticmethod
    def _cors_origins() -> tuple[str, ...]:
        raw = os.environ.get("TRINITY_API_CORS", "*")
        return tuple(value.strip() for value in raw.split(",") if value.strip())

    def security_check(self) -> tuple[bool, str]:
        return validate_api_exposure(
            self.host,
            pin_hash=os.environ.get("TRINITY_APP_PIN_HASH", ""),
            jwt_secret=os.environ.get("TRINITY_JWT_SECRET", DEFAULT_JWT_SECRET),
            remote_transport=os.environ.get("TRINITY_API_REMOTE_TRANSPORT", ""),
            tls_cert=os.environ.get("TRINITY_API_TLS_CERT", ""),
            tls_key=os.environ.get("TRINITY_API_TLS_KEY", ""),
            cors_origins=self._cors_origins(),
        )

    def start(self) -> bool:
        if self.server is not None:
            return True
        allowed, reason = self.security_check()
        if not allowed:
            self.error = reason
            return False
        try:
            import uvicorn
            from core import api as api_module

            api_module.set_runtime_brain(self.runtime)
            transport = os.environ.get("TRINITY_API_REMOTE_TRANSPORT", "").strip().lower()
            ssl_options = {}
            if transport == "https":
                ssl_options = {
                    "ssl_certfile": os.environ.get("TRINITY_API_TLS_CERT"),
                    "ssl_keyfile": os.environ.get("TRINITY_API_TLS_KEY"),
                }
            config = uvicorn.Config(
                api_module.app,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False,
                **ssl_options,
            )
            self.server = uvicorn.Server(config)
            self.thread = Thread(target=self.server.run, name="trinity-api", daemon=True)
            self.thread.start()
            return True
        except Exception as exc:
            self.error = str(exc)
            self.server = None
            self.thread = None
            return False

    def stop(self) -> None:
        server, thread = self.server, self.thread
        self.server = None
        self.thread = None
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5)
