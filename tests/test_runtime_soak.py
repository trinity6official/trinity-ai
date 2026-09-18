from datetime import datetime, timedelta

from core.events import EventBus
from core.process_manager import ProcessManager
from core.scheduler import PersistentScheduler


def test_scheduler_process_loop_survives_repeated_handler_and_observer_failures(tmp_path):
    """Fast deterministic soak across persistent scheduling and process execution."""
    bus = EventBus()
    successful_runs = []
    failed_runs = []

    def broken_observer(_event):
        raise RuntimeError("observer offline")

    bus.subscribe("process.succeeded", broken_observer)
    bus.subscribe("process.failed", lambda event: failed_runs.append(event.payload["process_id"]))
    processes = ProcessManager(tmp_path / "processes.db", event_bus=bus)
    scheduler = PersistentScheduler(processes, tmp_path / "schedules.db", event_bus=bus)
    counter = {"n": 0}

    def intermittent(_context, _payload):
        counter["n"] += 1
        if counter["n"] % 7 == 0:
            raise RuntimeError("simulated transient task failure")
        successful_runs.append(counter["n"])

    processes.register_handler("soak.heartbeat", intermittent)
    start = datetime(2026, 9, 15, 12, 0)
    scheduler.add_interval("heartbeat", 1, "soak.heartbeat", start_at=start)
    for second in range(1, 1001):
        scheduler.tick(current=start + timedelta(seconds=second))
        processes.run_next()

    assert counter["n"] == 1000
    assert len(failed_runs) == 1000 // 7
    assert len(successful_runs) == 1000 - len(failed_runs)
    assert bus.handler_errors
    assert len(bus.handler_errors) == 100
