from datetime import datetime

from core.events import EventBus
from core.scheduler import RuntimeScheduler


def test_scheduler_event_loop_survives_repeated_callback_and_observer_failures():
    """Fast deterministic soak: failures must remain isolated over many runtime ticks."""
    bus = EventBus()
    successful_runs = []
    failed_runs = []

    def broken_observer(_event):
        raise RuntimeError("observer offline")

    bus.subscribe("scheduler.task_completed", broken_observer)
    bus.subscribe("scheduler.task_failed", lambda event: failed_runs.append(event.payload["task"]))

    scheduler = RuntimeScheduler(bus)
    counter = {"n": 0}

    def intermittent():
        counter["n"] += 1
        if counter["n"] % 7 == 0:
            raise RuntimeError("simulated transient task failure")
        successful_runs.append(counter["n"])

    scheduler.add_interval("heartbeat", 1, intermittent, now_seconds=0)
    for second in range(1, 1001):
        scheduler.tick(
            current=datetime(2026, 9, 15, 12, 0),
            now_seconds=float(second),
        )

    assert counter["n"] == 1000
    assert len(failed_runs) == 1000 // 7
    assert len(successful_runs) == 1000 - len(failed_runs)
    # The broken observer was hit repeatedly, but its exceptions never escaped.
    assert bus.handler_errors
    assert len(bus.handler_errors) == 100
