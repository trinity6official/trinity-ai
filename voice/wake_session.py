"""Short-lived wake-session cache for Trinity Voice 2.0.

Speaker verification is intentionally performed once when a wake session opens.
Subsequent turns reuse the same trust context until inactivity expires the
session or it is explicitly closed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from time import monotonic
from typing import Callable
from uuid import uuid4

from core.trust_context import TrustContext
from voice.identity import SpeakerVerification, trust_context_for_voice


Clock = Callable[[], float]


@dataclass(frozen=True)
class WakeSession:
    session_id: str
    trust_context: TrustContext
    verification: SpeakerVerification | None
    started_at: float
    last_activity_at: float
    expires_at: float


class WakeSessionManager:
    """Cache speaker trust for a short conversational session."""

    def __init__(
        self,
        inactivity_seconds: float = 300.0,
        *,
        clock: Clock = monotonic,
    ) -> None:
        self.inactivity_seconds = max(1.0, float(inactivity_seconds))
        self._clock = clock
        self._session: WakeSession | None = None

    def _expire_if_needed(self) -> None:
        session = self._session
        if session is not None and self._clock() >= session.expires_at:
            self._session = None

    @property
    def current(self) -> WakeSession | None:
        self._expire_if_needed()
        return self._session

    @property
    def active(self) -> bool:
        return self.current is not None

    def open(
        self,
        *,
        verification: SpeakerVerification | None = None,
        trust_context: TrustContext | None = None,
    ) -> WakeSession:
        now = self._clock()
        context = trust_context or trust_context_for_voice(verification)
        self._session = WakeSession(
            session_id=uuid4().hex[:12],
            trust_context=context,
            verification=verification,
            started_at=now,
            last_activity_at=now,
            expires_at=now + self.inactivity_seconds,
        )
        return self._session

    def touch(self) -> WakeSession | None:
        session = self.current
        if session is None:
            return None
        now = self._clock()
        self._session = replace(
            session,
            last_activity_at=now,
            expires_at=now + self.inactivity_seconds,
        )
        return self._session

    def close(self) -> None:
        self._session = None

    def status(self) -> dict[str, object]:
        session = self.current
        if session is None:
            return {
                "active": False,
                "session_id": None,
                "trust_level": None,
                "speaker_verified": None,
                "expires_in_seconds": 0.0,
            }
        verification = session.verification
        return {
            "active": True,
            "session_id": session.session_id,
            "trust_level": session.trust_context.level.value,
            "speaker_verified": (
                verification.owner_verified if verification is not None else None
            ),
            "expires_in_seconds": max(0.0, session.expires_at - self._clock()),
        }
