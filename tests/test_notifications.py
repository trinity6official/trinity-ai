from unittest.mock import MagicMock

from core.events import EventBus
from core.notifications import NotificationService


def test_notification_is_local_event_by_default():
    bus = EventBus(); seen=[]; bus.subscribe("notification.created", seen.append)
    result = NotificationService(bus).notify("hello", category="test")
    assert result.event_created is True
    assert result.voice_spoken is False
    assert seen[0].payload["message"] == "hello"
    assert seen[0].payload["category"] == "test"


def test_notification_speaks_only_when_explicitly_requested():
    bus = EventBus(); voice = MagicMock(); voice.speak.return_value = True
    result = NotificationService(bus, voice=voice).notify("hello", speak=True)
    assert result.voice_spoken is True
    voice.speak.assert_called_once_with("hello")
