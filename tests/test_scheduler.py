from datetime import datetime, date

from core.events import EventBus
from core.scheduler import RuntimeScheduler


def test_interval_task_runs_when_due_and_emits_events():
    bus=EventBus(); events=[]; bus.subscribe("*", events.append); calls=[]
    scheduler=RuntimeScheduler(bus)
    scheduler.add_interval("proactive", 10, lambda: calls.append("x"), now_seconds=0)
    scheduler.tick(current=datetime(2026,9,15,1,0), now_seconds=9)
    assert calls == []
    scheduler.tick(current=datetime(2026,9,15,1,0), now_seconds=10)
    assert calls == ["x"]
    assert [e.type for e in events[-2:]] == ["scheduler.task_started", "scheduler.task_completed"]


def test_daily_task_runs_once_per_date_after_time():
    calls=[]; scheduler=RuntimeScheduler()
    scheduler.add_daily("brief", 6, 0, lambda: calls.append("brief"), last_run_date=date(2026,9,14))
    scheduler.tick(current=datetime(2026,9,15,5,59), now_seconds=0)
    assert calls == []
    scheduler.tick(current=datetime(2026,9,15,6,0), now_seconds=1)
    scheduler.tick(current=datetime(2026,9,15,8,0), now_seconds=2)
    assert calls == ["brief"]


def test_failed_task_does_not_block_other_due_tasks():
    bus = EventBus(); events = []
    bus.subscribe("*", lambda event: events.append(event.type))
    calls = []
    scheduler = RuntimeScheduler(bus)

    def fail():
        calls.append("bad")
        raise RuntimeError("temporary failure")

    scheduler.add_interval("bad", 10, fail, now_seconds=0)
    scheduler.add_interval("good", 10, lambda: calls.append("good"), now_seconds=0)
    scheduler.tick(current=datetime(2026, 9, 15, 1, 0), now_seconds=10)

    assert calls == ["bad", "good"]
    assert "scheduler.task_failed" in events
    assert events.count("scheduler.task_completed") == 1
