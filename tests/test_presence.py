from core.events import EventBus
from core.presence import PresenceEngine, PresenceState


def test_presence_follows_message_and_tool_lifecycle():
    now = [0.0]
    bus = EventBus(); presence = PresenceEngine(bus, done_duration=1.0, clock=lambda: now[0])
    assert presence.snapshot().state == PresenceState.IDLE
    bus.publish("message.received", text="hello")
    assert presence.snapshot().state == PresenceState.THINKING
    bus.publish("tool.started", tool="github.read_file")
    snap = presence.snapshot()
    assert snap.state == PresenceState.USING_TOOL
    assert snap.active_tool == "github.read_file"
    bus.publish("tool.completed", tool="github.read_file")
    assert presence.snapshot().state == PresenceState.THINKING
    bus.publish("message.completed", kind="conversation")
    assert presence.snapshot().state == PresenceState.DONE
    now[0] = 1.1
    assert presence.snapshot().state == PresenceState.IDLE


def test_presence_has_explicit_search_state():
    bus = EventBus(); presence = PresenceEngine(bus)
    bus.publish("tool.started", tool="search.web")
    assert presence.snapshot().state == PresenceState.SEARCHING
    bus.publish("action.started", actor_type="skill", action="web.search")
    assert presence.snapshot().state == PresenceState.SEARCHING


def test_presence_follows_voice_states():
    bus = EventBus(); presence = PresenceEngine(bus)
    for raw, expected in [
        ("listening", PresenceState.LISTENING),
        ("thinking", PresenceState.THINKING),
        ("speaking", PresenceState.SPEAKING),
        ("idle", PresenceState.IDLE),
    ]:
        bus.publish("voice.state", state=raw)
        assert presence.snapshot().state == expected


def test_presence_marks_computer_or_agent_execution():
    bus = EventBus(); presence = PresenceEngine(bus)
    bus.publish("action.started", actor_type="computer", action="computer.open_app")
    assert presence.snapshot().state == PresenceState.EXECUTING
    bus.publish("action.started", actor_type="skill", action="github.read_file")
    assert presence.snapshot().state == PresenceState.USING_TOOL


def test_presence_surfaces_runtime_error_and_can_clear():
    bus = EventBus(); presence = PresenceEngine(bus)
    bus.publish("tool.failed", tool="x", error="boom")
    assert presence.snapshot().state == PresenceState.ERROR
    assert presence.snapshot().error == "boom"
    presence.clear_error()
    assert presence.snapshot().state == PresenceState.IDLE
