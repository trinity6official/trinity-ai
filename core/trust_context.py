"""Request trust context for Trinity authorization decisions.

Trust is based on who/what issued a request, not whether the Mac screen is
locked.  Screen lock is retained as context for auditing/future policy, but it
does not automatically disable David's local or authenticated remote access.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Mapping


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    VERIFIED_REMOTE = "verified_remote"
    UNVERIFIED = "unverified"


class RequestSource(str, Enum):
    LOCAL_RUNTIME = "local_runtime"
    LOCAL_UI = "local_ui"
    LOCAL_VOICE = "local_voice"
    REMOTE_API = "remote_api"
    AGENT = "agent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TrustContext:
    source: RequestSource = RequestSource.UNKNOWN
    authenticated: bool = False
    owner_verified: bool = False
    subject: str | None = None
    device_id: str | None = None
    screen_locked: bool | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def level(self) -> TrustLevel:
        if self.source in {RequestSource.LOCAL_RUNTIME, RequestSource.LOCAL_UI}:
            if self.authenticated or self.owner_verified:
                return TrustLevel.TRUSTED
        if self.source == RequestSource.LOCAL_VOICE and self.owner_verified:
            return TrustLevel.TRUSTED
        if self.source == RequestSource.REMOTE_API and self.authenticated:
            return TrustLevel.VERIFIED_REMOTE
        return TrustLevel.UNVERIFIED

    @property
    def can_approve(self) -> bool:
        return self.level in {TrustLevel.TRUSTED, TrustLevel.VERIFIED_REMOTE}

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "level": self.level.value,
            "authenticated": self.authenticated,
            "owner_verified": self.owner_verified,
            "subject": self.subject,
            "device_id": self.device_id,
            "screen_locked": self.screen_locked,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def local_trusted(
        cls,
        *,
        source: RequestSource = RequestSource.LOCAL_RUNTIME,
        subject: str = "david",
        screen_locked: bool | None = None,
    ) -> "TrustContext":
        return cls(
            source=source,
            authenticated=True,
            owner_verified=True,
            subject=subject,
            screen_locked=screen_locked,
        )

    @classmethod
    def verified_remote(
        cls,
        *,
        subject: str = "david",
        device_id: str | None = None,
        screen_locked: bool | None = None,
    ) -> "TrustContext":
        return cls(
            source=RequestSource.REMOTE_API,
            authenticated=True,
            owner_verified=True,
            subject=subject,
            device_id=device_id,
            screen_locked=screen_locked,
        )

    @classmethod
    def unverified(
        cls,
        *,
        source: RequestSource = RequestSource.UNKNOWN,
        screen_locked: bool | None = None,
    ) -> "TrustContext":
        return cls(source=source, screen_locked=screen_locked)


_CURRENT_TRUST: ContextVar[TrustContext | None] = ContextVar(
    "trinity_current_trust_context", default=None
)


def get_current_trust_context() -> TrustContext:
    """Return request trust, defaulting legacy local runtime to trusted.

    Existing Trinity entry points are local-only today.  As new entry points are
    added they should explicitly set their context.  The authenticated HTTP API
    does this for remote requests; ambient voice can later set UNVERIFIED until
    speaker verification succeeds.
    """
    context = _CURRENT_TRUST.get()
    return context if context is not None else TrustContext.local_trusted()


@contextmanager
def use_trust_context(context: TrustContext) -> Iterator[TrustContext]:
    token = _CURRENT_TRUST.set(context)
    try:
        yield context
    finally:
        _CURRENT_TRUST.reset(token)
