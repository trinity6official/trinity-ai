from core.trust_context import RequestSource, TrustContext, TrustLevel
from voice.identity import SpeakerVerification, SpeakerVerificationStatus
from voice.wake_session import WakeSessionManager


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def verified_david():
    return SpeakerVerification(
        SpeakerVerificationStatus.VERIFIED,
        speaker_id="david",
        confidence=0.98,
    )


def test_wake_session_caches_verified_trust():
    clock = FakeClock()
    manager = WakeSessionManager(30, clock=clock)
    session = manager.open(verification=verified_david())

    assert manager.active is True
    assert session.trust_context.level == TrustLevel.TRUSTED
    assert manager.status()["speaker_verified"] is True


def test_touch_extends_inactivity_window():
    clock = FakeClock()
    manager = WakeSessionManager(30, clock=clock)
    first = manager.open(verification=verified_david())

    clock.advance(20)
    touched = manager.touch()
    assert touched is not None
    assert touched.expires_at > first.expires_at

    clock.advance(20)
    assert manager.active is True


def test_session_expires_after_inactivity():
    clock = FakeClock()
    manager = WakeSessionManager(10, clock=clock)
    manager.open(verification=verified_david())

    clock.advance(10)
    assert manager.active is False
    assert manager.current is None


def test_close_immediately_drops_cached_trust():
    manager = WakeSessionManager()
    manager.open(
        trust_context=TrustContext.local_trusted(
            source=RequestSource.LOCAL_VOICE,
            subject="david",
        )
    )
    manager.close()

    assert manager.active is False
    assert manager.status()["trust_level"] is None
