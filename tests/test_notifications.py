from unittest.mock import MagicMock

from core.events import EventBus
from core.notifications import NotificationService


def test_notification_is_local_event_by_default():
    bus = EventBus(); seen=[]; bus.subscribe("notification.created", seen.append)
    telegram = MagicMock(); telegram.remote_notifications = False
    result = NotificationService(bus, telegram=telegram).notify("hello", category="test")
    assert result.event_created is True
    assert result.telegram_sent is False
    telegram.send.assert_not_called()
    assert seen[0].payload["message"] == "hello"


def test_remote_notification_requires_explicit_opt_in():
    bus = EventBus(); telegram = MagicMock(); telegram.remote_notifications = True
    telegram.send.return_value = True
    result = NotificationService(bus, telegram=telegram).notify("hello")
    assert result.telegram_sent is True
    telegram.send.assert_called_once_with("hello")
