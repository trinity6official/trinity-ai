import sqlite3

from core.audit import ActionAuditTrail
from core.events import EventBus
from core.process_manager import (
    ProcessCancelled,
    ProcessManager,
    ProcessStatus,
)


def test_submit_persists_and_survives_reopen(tmp_path):
    path = tmp_path / "processes.db"
    manager = ProcessManager(path)
    process = manager.submit("demo", {"items": [1, 2]}, max_retries=2, timeout_seconds=30)
    reopened = ProcessManager(path)
    loaded = reopened.get(process.id)
    assert loaded is not None
    assert loaded.status == ProcessStatus.QUEUED
    assert loaded.payload["items"] == (1, 2)
    assert loaded.max_retries == 2


def test_run_success_updates_progress_result_events_and_audit(tmp_path):
    bus = EventBus()
    seen = []
    bus.subscribe("*", lambda event: seen.append(event.type))
    audit = ActionAuditTrail(tmp_path / "audit.jsonl")
    manager = ProcessManager(tmp_path / "processes.db", event_bus=bus, audit_trail=audit)

    def handler(ctx, payload):
        ctx.checkpoint(0.4)
        return {"value": payload["value"] + 1}

    manager.register_handler("demo", handler)
    process = manager.submit("demo", {"value": 4})
    result = manager.run(process.id)
    assert result.status == ProcessStatus.SUCCEEDED
    assert result.progress == 1.0
    assert result.result == {"value": 5}
    assert "process.started" in seen
    assert "process.progress" in seen
    assert "process.succeeded" in seen
    assert "\"actor_type\": \"process\"" in (tmp_path / "audit.jsonl").read_text()


def test_failure_requeues_until_retry_budget_exhausted(tmp_path):
    manager = ProcessManager(tmp_path / "processes.db")
    manager.register_handler("boom", lambda *_: (_ for _ in ()).throw(RuntimeError("nope")))
    process = manager.submit("boom", {}, max_retries=1)
    first = manager.run(process.id)
    assert first.status == ProcessStatus.QUEUED
    assert first.attempts == 1
    second = manager.run(process.id)
    assert second.status == ProcessStatus.FAILED
    assert second.attempts == 2
    assert "nope" in second.error


def test_queued_cancel_is_terminal_and_never_runs(tmp_path):
    manager = ProcessManager(tmp_path / "processes.db")
    called = []
    manager.register_handler("demo", lambda *_: called.append(True))
    process = manager.submit("demo")
    assert manager.request_cancel(process.id) is True
    final = manager.run(process.id)
    assert final.status == ProcessStatus.CANCELLED
    assert called == []


def test_running_process_observes_cooperative_cancel(tmp_path):
    manager = ProcessManager(tmp_path / "processes.db")

    def handler(ctx, _payload):
        manager.request_cancel(ctx.process_id)
        ctx.checkpoint(0.5)

    manager.register_handler("demo", handler)
    process = manager.submit("demo")
    final = manager.run(process.id)
    assert final.status == ProcessStatus.CANCELLED


def test_timeout_is_enforced_at_process_checkpoint(tmp_path):
    now = [100.0]
    manager = ProcessManager(tmp_path / "processes.db", clock=lambda: now[0])

    def handler(ctx, _payload):
        now[0] = 103.0
        ctx.checkpoint()

    manager.register_handler("demo", handler)
    process = manager.submit("demo", timeout_seconds=2)
    final = manager.run(process.id)
    assert final.status == ProcessStatus.TIMED_OUT
    assert "deadline" in final.error.lower()


def test_restart_requeues_interrupted_work_when_retry_budget_remains(tmp_path):
    path = tmp_path / "processes.db"
    manager = ProcessManager(path)
    process = manager.submit("demo", {}, max_retries=1)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE processes SET status=?, attempts=1 WHERE id=?",
            (ProcessStatus.RUNNING.value, process.id),
        )
    reopened = ProcessManager(path)
    recovered = reopened.get(process.id)
    assert recovered.status == ProcessStatus.QUEUED
    assert recovered.error == "Interrupted by runtime restart"


def test_restart_fails_interrupted_work_without_retry_budget(tmp_path):
    path = tmp_path / "processes.db"
    manager = ProcessManager(path)
    process = manager.submit("demo", {}, max_retries=0)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE processes SET status=?, attempts=1 WHERE id=?",
            (ProcessStatus.RUNNING.value, process.id),
        )
    reopened = ProcessManager(path)
    assert reopened.get(process.id).status == ProcessStatus.FAILED


def test_run_next_uses_oldest_queued_process(tmp_path):
    manager = ProcessManager(tmp_path / "processes.db")
    seen = []
    manager.register_handler("demo", lambda _ctx, payload: seen.append(payload["id"]) or payload["id"])
    first = manager.submit("demo", {"id": 1}, process_id="a")
    manager.submit("demo", {"id": 2}, process_id="b")
    result = manager.run_next()
    assert result.id == first.id
    assert seen == [1]


def test_process_payload_is_immutable_snapshot(tmp_path):
    manager = ProcessManager(tmp_path / "processes.db")
    payload = {"nested": {"items": [1]}}
    process = manager.submit("demo", payload)
    payload["nested"]["items"].append(2)
    assert manager.get(process.id).payload["nested"]["items"] == (1,)
