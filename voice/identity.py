"""Speaker-identity contracts for Trinity Voice 2.0.

This module intentionally contains no model implementation.  Hardware-specific
speaker embedding/verification providers can implement ``SpeakerVerifier`` later
without changing the voice-session or authorization layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from core.trust_context import RequestSource, TrustContext


class SpeakerVerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpeakerVerification:
    status: SpeakerVerificationStatus
    speaker_id: str | None = None
    confidence: float | None = None
    reason: str | None = None

    @property
    def verified(self) -> bool:
        return self.status == SpeakerVerificationStatus.VERIFIED

    @property
    def owner_verified(self) -> bool | None:
        if self.status == SpeakerVerificationStatus.VERIFIED:
            return True
        if self.status == SpeakerVerificationStatus.UNVERIFIED:
            return False
        return None


class SpeakerVerifier(Protocol):
    """Provider contract for future local speaker verification."""

    def verify(self, audio_file: str) -> SpeakerVerification:
        ...


def trust_context_for_voice(
    verification: SpeakerVerification | None,
    *,
    screen_locked: bool | None = None,
) -> TrustContext:
    """Convert speaker identity evidence into Trinity's request trust context."""
    if verification is not None and verification.verified:
        return TrustContext(
            source=RequestSource.LOCAL_VOICE,
            owner_verified=True,
            subject=verification.speaker_id or "david",
            screen_locked=screen_locked,
            metadata={
                "speaker_verification": verification.status.value,
                "speaker_confidence": verification.confidence,
            },
        )

    metadata = {}
    if verification is not None:
        metadata = {
            "speaker_verification": verification.status.value,
            "speaker_confidence": verification.confidence,
            "speaker_reason": verification.reason,
        }
    return TrustContext(
        source=RequestSource.LOCAL_VOICE,
        screen_locked=screen_locked,
        metadata=metadata,
    )
