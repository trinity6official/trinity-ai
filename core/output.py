"""Channel-neutral response routing for Trinity.

User-facing services emit through this boundary instead of knowing which
interface initiated a request.  The active request may bind an API, mobile,
voice, CLI, or future responder without coupling core reasoning to a transport.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


Responder = Callable[[str], Any]


class ResponseRouter:
    """Route user-facing output to the responder bound to the current request."""

    def __init__(self, event_bus: Any = None, *, default_responder: Responder | None = None) -> None:
        self.event_bus = event_bus
        self.default_responder = default_responder
        self._responder: ContextVar[Responder | None] = ContextVar(
            "trinity_response_responder", default=None
        )
        self._source: ContextVar[str] = ContextVar("trinity_response_source", default="local")

    @contextmanager
    def route(self, responder: Responder | None, *, source: str = "local") -> Iterator[None]:
        """Bind a responder for one request without leaking it across threads/tasks."""
        responder_token = self._responder.set(responder)
        source_token = self._source.set(str(source or "local"))
        try:
            yield
        finally:
            self._source.reset(source_token)
            self._responder.reset(responder_token)

    def emit(self, message: str, *, kind: str = "message") -> bool:
        """Publish and deliver one user-facing message through the active route."""
        text = str(message)
        source = self._source.get()
        if self.event_bus is not None:
            self.event_bus.publish(
                "response.emitted",
                message=text,
                source=source,
                kind=kind,
            )

        responder = self._responder.get() or self.default_responder
        if responder is None:
            return False
        result = responder(text)
        return result is not False
