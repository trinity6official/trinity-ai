from types import SimpleNamespace
from unittest.mock import MagicMock

from core.events import Event, EventBus
from core.proactive_events import ProactiveEventEngine, ProactiveEventService


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_scheduler_failure_alerts_immediately():
    engine = ProactiveEventEngine(clock=lambda: 100.0)
    signal = engine.observe(
        Event("scheduler.task_failed", {"task": "backup", "error": "disk full"})
    )
    assert signal is not None
    assert signal.urgent is True
    assert "backup" in signal.message
    assert "disk full" in signal.message


def test_tool_failures_require_threshold():
    clock = FakeClock()
    engine = ProactiveEventEngine(clock=clock)
    event = Event("tool.failed", {"tool": "github.update_file", "error": "timeout"})

    assert engine.observe(event) is None
    assert engine.observe(event) is None
    signal = engine.observe(event)

    assert signal is not None
    assert "3 times" in signal.message


def test_tool_failure_counts_are_isolated_by_tool():
    engine = ProactiveEventEngine(clock=lambda: 100.0)
    a = Event("tool.failed", {"tool": "github.read_file", "error": "a"})
    b = Event("tool.failed", {"tool": "computer.run_command", "error": "b"})

    assert engine.observe(a) is None
    assert engine.observe(a) is None
    assert engine.observe(b) is None
    assert engine.observe(b) is None
    assert engine.observe(a) is not None
    assert engine.observe(b) is not None


def test_cooldown_suppresses_repeat_alert():
    clock = FakeClock()
    engine = ProactiveEventEngine(clock=clock)
    event = Event("scheduler.task_failed", {"task": "backup", "error": "disk full"})

    assert engine.observe(event) is not None
    clock.advance(60)
    assert engine.observe(event) is None
    clock.advance(300)
    assert engine.observe(event) is not None


def test_old_failures_fall_outside_threshold_window():
    clock = FakeClock()
    engine = ProactiveEventEngine(clock=clock)
    event = Event("voice.runtime_error", {"error": "mic unavailable"})

    assert engine.observe(event) is None
    assert engine.observe(event) is None
    clock.advance(301)
    assert engine.observe(event) is None


def test_service_notifies_without_calling_llm():
    bus = EventBus()
    host = SimpleNamespace(
        events=bus,
        notify=MagicMock(),
        permissions=SimpleNamespace(
            assess_action=lambda action: SimpleNamespace(allowed_autonomously=True)
        ),
        _invoke_with_failover=MagicMock(),
    )
    service = ProactiveEventService(host)
    service.start()

    bus.publish("scheduler.task_failed", task="morning_briefing", error="boom")

    host.notify.assert_called_once()
    host._invoke_with_failover.assert_not_called()


def test_service_permission_gate_can_suppress_event_alert():
    bus = EventBus()
    suppressed = []
    bus.subscribe("proactive.event_suppressed", suppressed.append)
    host = SimpleNamespace(
        events=bus,
        notify=MagicMock(),
        permissions=SimpleNamespace(
            assess_action=lambda action: SimpleNamespace(allowed_autonomously=False)
        ),
    )
    service = ProactiveEventService(host)
    service.start()

    bus.publish("scheduler.task_failed", task="backup", error="boom")

    host.notify.assert_not_called()
    assert len(suppressed) == 1
    assert suppressed[0].payload["reason"] == "permission"


def test_service_stop_unsubscribes_cleanly():
    bus = EventBus()
    host = SimpleNamespace(
        events=bus,
        notify=MagicMock(),
        permissions=SimpleNamespace(
            assess_action=lambda action: SimpleNamespace(allowed_autonomously=True)
        ),
    )
    service = ProactiveEventService(host)
    service.start()
    service.stop()

    bus.publish("scheduler.task_failed", task="backup", error="boom")
    host.notify.assert_not_called()


def test_skill_gap_event_becomes_user_visible_without_self_modification():
    bus = EventBus()
    host = SimpleNamespace(
        events=bus,
        notify=MagicMock(),
        permissions=SimpleNamespace(
            assess_action=lambda action: SimpleNamespace(allowed_autonomously=True)
        ),
    )
    service = ProactiveEventService(host)
    service.start()

    bus.publish(
        "proactive.skill_approval_required",
        skill="calendar",
        reason="Need calendar conflict awareness",
    )

    args, kwargs = host.notify.call_args
    assert "calendar" in args[0]
    assert "approval" in args[0].lower()
    assert kwargs["category"] == "proactive"
