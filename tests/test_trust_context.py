from core.trust_context import (
    RequestSource,
    TrustContext,
    TrustLevel,
    get_current_trust_context,
    use_trust_context,
)


def test_legacy_local_default_is_trusted():
    assert get_current_trust_context().level == TrustLevel.TRUSTED


def test_verified_remote_is_not_downgraded_by_locked_screen():
    context = TrustContext.verified_remote(
        subject="david", device_id="phone", screen_locked=True
    )
    assert context.level == TrustLevel.VERIFIED_REMOTE
    assert context.can_approve is True


def test_ambient_voice_is_unverified_without_owner_verification():
    context = TrustContext.unverified(
        source=RequestSource.LOCAL_VOICE, screen_locked=True
    )
    assert context.level == TrustLevel.UNVERIFIED
    assert context.can_approve is False


def test_verified_local_voice_can_be_trusted():
    context = TrustContext(
        source=RequestSource.LOCAL_VOICE,
        owner_verified=True,
        subject="david",
        screen_locked=True,
    )
    assert context.level == TrustLevel.TRUSTED


def test_context_manager_restores_previous_context():
    original = get_current_trust_context()
    remote = TrustContext.verified_remote(subject="david")
    with use_trust_context(remote):
        assert get_current_trust_context() == remote
    assert get_current_trust_context().level == original.level


def test_context_serialization_contains_policy_relevant_fields():
    context = TrustContext.verified_remote(
        subject="david", device_id="phone", screen_locked=True
    )
    data = context.to_dict()
    assert data["level"] == "verified_remote"
    assert data["source"] == "remote_api"
    assert data["screen_locked"] is True
