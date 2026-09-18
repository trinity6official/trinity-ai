from datetime import datetime, timedelta

import pytest

from core.events import EventBus
from core.process_manager import ProcessManager, ProcessStatus
from core.scheduler import PersistentScheduler, ScheduleKind


def _pair(tmp_path, bus=None):
    processes = ProcessManager(tmp_path / "processes.db", event_bus=bus)
    scheduler = PersistentScheduler(processes, tmp_path / "schedules.db", event_bus=bus)
    return processes, scheduler


def test_once_schedule_submits_one_durable_process_and_snapshots_payload(tmp_path):
    processes, scheduler = _pair(tmp_path)
    due = datetime(2026, 9, 15, 12, 0)
    payload = {"items": ["a"]}
    record = scheduler.add_once("report", due, "report.generate", payload)
    payload["items"].append("mutated")

    assert record.kind == ScheduleKind.ONCE
    assert list(record.payload["items"]) == ["a"]
    submitted = scheduler.tick(current=due)
    assert len(submitted) == 1
    assert submitted[0].kind == "report.generate"
    assert list(submitted[0].payload["items"]) == ["a"]
    assert scheduler.tick(current=due + timedelta(hours=1)) == []
    assert scheduler.get("report").enabled is False


def test_interval_schedule_persists_and_skips_downtime_burst(tmp_path):
    processes, scheduler = _pair(tmp_path)
    start = datetime(2026, 9, 15, 12, 0)
    scheduler.add_interval("heartbeat", 10, "system.heartbeat", start_at=start)

    assert scheduler.tick(current=start + timedelta(seconds=9)) == []
    assert len(scheduler.tick(current=start + timedelta(seconds=10))) == 1

    restarted = PersistentScheduler(processes, tmp_path / "schedules.db")
    record = restarted.get("heartbeat")
    assert record is not None
    assert record.next_run_at == start + timedelta(seconds=20)

    # A long restart does not enqueue every missed 10-second occurrence.
    assert len(restarted.tick(current=start + timedelta(seconds=35))) == 1
    assert restarted.get("heartbeat").next_run_at == start + timedelta(seconds=40)


def test_daily_schedule_runs_once_per_day_and_survives_restart(tmp_path):
    processes, scheduler = _pair(tmp_path)
    start = datetime(2026, 9, 15, 5, 0)
    scheduler.add_daily("brief", 6, 0, "briefing.morning", start_at=start)

    assert scheduler.tick(current=datetime(2026, 9, 15, 5, 59)) == []
    assert len(scheduler.tick(current=datetime(2026, 9, 15, 6, 0))) == 1

    restarted = PersistentScheduler(processes, tmp_path / "schedules.db")
    assert restarted.tick(current=datetime(2026, 9, 15, 20, 0)) == []
    assert restarted.get("brief").next_run_at == datetime(2026, 9, 16, 6, 0)
    assert len(restarted.tick(current=datetime(2026, 9, 16, 6, 0))) == 1


def test_submission_is_idempotent_across_crash_window(tmp_path):
    processes, scheduler = _pair(tmp_path)
    due = datetime(2026, 9, 15, 12, 0)
    schedule = scheduler.add_once("export", due, "export.run", start_payload := {"x": 1})
    process_id = scheduler._process_id(schedule)

    # Simulate a crash after ProcessManager insert but before schedule advancement.
    processes.submit("export.run", start_payload, process_id=process_id)
    assert scheduler.tick(current=due) == []
    assert scheduler.get("export").enabled is False
    assert len(processes.list()) == 1


def test_pause_and_resume_are_persistent(tmp_path):
    processes, scheduler = _pair(tmp_path)
    start = datetime(2026, 9, 15, 12, 0)
    scheduler.add_interval("refresh", 60, "refresh.run", start_at=start)
    scheduler.pause("refresh")
    assert scheduler.get("refresh").enabled is False

    restarted = PersistentScheduler(processes, tmp_path / "schedules.db")
    assert restarted.tick(current=start + timedelta(minutes=2)) == []
    restarted.resume("refresh")
    assert restarted.get("refresh").enabled is True
    assert len(restarted.tick(current=start + timedelta(minutes=2))) == 1


def test_schedule_execution_is_owned_by_process_manager(tmp_path):
    bus = EventBus()
    events = []
    bus.subscribe("*", events.append)
    processes, scheduler = _pair(tmp_path, bus)
    calls = []
    processes.register_handler(
        "demo.run",
        lambda context, payload: calls.append(payload["value"]) or {"ok": True},
    )
    now = datetime(2026, 9, 15, 12, 0)
    scheduler.add_once("demo", now, "demo.run", {"value": 7})

    submitted = scheduler.tick(current=now)
    assert calls == []
    assert submitted[0].status == ProcessStatus.QUEUED
    completed = processes.run_next()
    assert calls == [7]
    assert completed.status == ProcessStatus.SUCCEEDED
    assert any(event.type == "scheduler.task_submitted" for event in events)


def test_invalid_schedule_values_are_rejected(tmp_path):
    _, scheduler = _pair(tmp_path)
    now = datetime(2026, 9, 15, 12, 0)
    with pytest.raises(ValueError):
        scheduler.add_interval("bad", 0, "bad.run", start_at=now)
    with pytest.raises(ValueError):
        scheduler.add_daily("bad", 25, 0, "bad.run", start_at=now)
