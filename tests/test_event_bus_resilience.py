from core.events import EventBus


def test_bad_subscriber_does_not_break_publisher_or_other_subscribers():
    bus = EventBus()
    seen = []

    def bad(_event):
        raise RuntimeError("observer failed")

    bus.subscribe("runtime.tick", bad)
    bus.subscribe("runtime.tick", lambda event: seen.append(event.payload["n"]))

    event = bus.publish("runtime.tick", n=1)

    assert event.type == "runtime.tick"
    assert seen == [1]
    assert bus.handler_errors[-1]["event_type"] == "runtime.tick"
    assert bus.handler_errors[-1]["error"] == "observer failed"


def test_event_bus_bounds_observer_error_history():
    bus = EventBus()

    def bad(_event):
        raise RuntimeError("boom")

    bus.subscribe("tick", bad)
    for i in range(125):
        bus.publish("tick", n=i)

    assert len(bus.handler_errors) == 100
