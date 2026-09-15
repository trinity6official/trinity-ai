from core.awareness import AwarenessEngine
from core.events import EventBus


def test_event_bus_delivers_specific_and_wildcard_subscribers():
    bus = EventBus()
    seen = []
    bus.subscribe("message.received", lambda event: seen.append(("specific", event.type)))
    bus.subscribe("*", lambda event: seen.append(("all", event.type)))
    bus.publish("message.received", text="hello")
    assert seen == [("specific", "message.received"), ("all", "message.received")]


def test_awareness_tracks_user_message():
    bus = EventBus(); awareness = AwarenessEngine(bus)
    bus.publish("message.received", text="hello Trinity")
    assert awareness.snapshot().last_user_message == "hello Trinity"


def test_awareness_tracks_active_tool_lifecycle():
    bus = EventBus(); awareness = AwarenessEngine(bus)
    bus.publish("tool.started", tool="github.read_file")
    assert awareness.snapshot().active_tool == "github.read_file"
    bus.publish("tool.completed", tool="github.read_file")
    assert awareness.snapshot().active_tool is None


def test_awareness_tracks_failures():
    bus = EventBus(); awareness = AwarenessEngine(bus)
    bus.publish("tool.failed", tool="web.check", error="timeout")
    assert awareness.snapshot().last_error == "timeout"


def test_recent_events_can_be_filtered():
    bus = EventBus(); awareness = AwarenessEngine(bus)
    bus.publish("message.received", text="one")
    bus.publish("tool.started", tool="x")
    bus.publish("message.received", text="two")
    assert [event.payload["text"] for event in awareness.recent("message.received")] == ["one", "two"]


def test_awareness_tracks_scheduler_and_daemon_state():
    bus = EventBus(); awareness = AwarenessEngine(bus)
    bus.publish("daemon.started")
    bus.publish("scheduler.task_started", task="proactive_check")
    snap = awareness.snapshot()
    assert snap.daemon_active is True
    assert snap.last_scheduler_task == "proactive_check"
    bus.publish("scheduler.task_completed", task="proactive_check")
    bus.publish("daemon.stopped")
    snap = awareness.snapshot()
    assert snap.daemon_active is False
    assert snap.last_scheduler_task is None


def test_awareness_tracks_local_screen_context_without_event_payload():
    bus = EventBus(); awareness = AwarenessEngine(bus)
    awareness.update_visual_context("Terminal", "Tests are running")
    snap = awareness.snapshot()
    assert snap.frontmost_app == "Terminal"
    assert snap.last_visual_context == "Tests are running"
