from core.trust_context import TrustLevel
from voice.identity import (
    SpeakerVerification,
    SpeakerVerificationStatus,
    trust_context_for_voice,
)


def test_verified_owner_maps_to_trusted_local_voice():
    verification = SpeakerVerification(
        SpeakerVerificationStatus.VERIFIED,
        speaker_id="david",
        confidence=0.99,
    )
    context = trust_context_for_voice(verification, screen_locked=True)
    assert context.level == TrustLevel.TRUSTED
    assert context.owner_verified is True
    assert context.screen_locked is True
    assert context.metadata["speaker_confidence"] == 0.99


def test_unknown_speaker_maps_to_unverified():
    context = trust_context_for_voice(
        SpeakerVerification(
            SpeakerVerificationStatus.UNKNOWN,
            reason="not enough audio",
        )
    )
    assert context.level == TrustLevel.UNVERIFIED
    assert context.owner_verified is False
    assert context.metadata["speaker_reason"] == "not enough audio"


def test_explicit_non_owner_maps_to_unverified():
    verification = SpeakerVerification(
        SpeakerVerificationStatus.UNVERIFIED,
        speaker_id="guest",
        confidence=0.95,
    )
    context = trust_context_for_voice(verification)
    assert verification.owner_verified is False
    assert context.level == TrustLevel.UNVERIFIED


def test_no_speaker_provider_is_unverified():
    assert trust_context_for_voice(None).level == TrustLevel.UNVERIFIED
