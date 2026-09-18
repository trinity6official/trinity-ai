"""Durable process orchestration for long-running Trinity work.

The ProcessManager owns lifecycle state only. It does not execute skills or agents
by itself; registered handlers may delegate into Trinity's existing governed
execution boundaries.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from core.audit import ActionAuditTrail
from core.events import EventBus
from core.execution import freeze_mapping, thaw_mapping


class ProcessStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


_TERMINAL = {
    ProcessStatus.SUCCEEDED,
    ProcessStatus.FAILED,
    ProcessStatus.CANCELLED,
    ProcessStatus.TIMED_OUT,
}


class ProcessCancelled(RuntimeError):
    pass


class ProcessTimedOut(TimeoutError):
    pass


@dataclass(frozen=True)
class ProcessRecord:
    id: str
    kind: str
    payload: Mapping[str, Any]
    status: ProcessStatus
    progress: float
    attempts: int
    max_retries: int
    timeout_seconds: float | None
    cancel_requested: bool
    result: Any
    error: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None

    @property
    def terminal(self) -> bool:
        return self.status in _TERMINAL


Handler = Callable[["ProcessContext", Mapping[str, Any]], Any]


class ProcessContext:
    """Cooperative progress/cancellation/timeout boundary passed to handlers."""

    def __init__(self, manager: "ProcessManager", process_id: str, deadline: float | None):
        self.manager = manager
        self.process_id = process_id
        self.deadline = deadline

    def checkpoint(self, progress: float | None = None) -> None:
        record = self.manager.get(self.process_id)
        if record is None:
            raise ProcessCancelled("Process no longer exists")
        if record.cancel_requested:
            raise ProcessCancelled("Cancellation requested")
        if self.deadline is not None and self.manager.clock() >= self.deadline:
            raise ProcessTimedOut("Process deadline exceeded")
        if progress is not None:
            self.manager.update_progress(self.process_id, progress)


class ProcessManager:
    """Persist and run resumable process lifecycle state in SQLite."""

    def __init__(
        self,
        path: str | Path = "memory/runtime/processes.db",
        *,
        event_bus: EventBus | None = None,
        audit_trail: ActionAuditTrail | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.audit = audit_trail
        self.clock = clock
        self._handlers: dict[str, Handler] = {}
        self._initialize()
        self.recover_interrupted()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processes (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 0,
                    timeout_seconds REAL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_process_status_created ON processes(status, created_at)"
            )

    def register_handler(self, kind: str, handler: Handler) -> None:
        normalized = str(kind).strip()
        if not normalized:
            raise ValueError("Process kind cannot be empty")
        self._handlers[normalized] = handler

    def submit(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        max_retries: int = 0,
        timeout_seconds: float | None = None,
        process_id: str | None = None,
    ) -> ProcessRecord:
        kind = str(kind).strip()
        if not kind:
            raise ValueError("Process kind cannot be empty")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        frozen = freeze_mapping(payload)
        now = self._now()
        pid = process_id or uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO processes (
                    id, kind, payload_json, status, progress, attempts, max_retries,
                    timeout_seconds, cancel_requested, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, 0, ?, ?, 0, ?, ?)
                """,
                (pid, kind, json.dumps(thaw_mapping(frozen), sort_keys=True), ProcessStatus.QUEUED.value,
                 max_retries, timeout_seconds, now, now),
            )
        self._emit("process.submitted", process_id=pid, kind=kind)
        self._audit("requested", pid, kind, params=thaw_mapping(frozen))
        return self.get(pid)  # type: ignore[return-value]

    def _row_to_record(self, row: sqlite3.Row) -> ProcessRecord:
        payload = json.loads(row["payload_json"])
        result = json.loads(row["result_json"]) if row["result_json"] is not None else None
        return ProcessRecord(
            id=row["id"], kind=row["kind"], payload=freeze_mapping(payload),
            status=ProcessStatus(row["status"]), progress=float(row["progress"]),
            attempts=int(row["attempts"]), max_retries=int(row["max_retries"]),
            timeout_seconds=row["timeout_seconds"], cancel_requested=bool(row["cancel_requested"]),
            result=result, error=row["error"], created_at=row["created_at"], updated_at=row["updated_at"],
            started_at=row["started_at"], finished_at=row["finished_at"],
        )

    def get(self, process_id: str) -> ProcessRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM processes WHERE id = ?", (process_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list(self, *, status: ProcessStatus | str | None = None, limit: int = 100) -> list[ProcessRecord]:
        with self._connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM processes ORDER BY created_at DESC LIMIT ?", (max(1, int(limit)),)
                ).fetchall()
            else:
                value = ProcessStatus(status).value
                rows = conn.execute(
                    "SELECT * FROM processes WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (value, max(1, int(limit))),
                ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def request_cancel(self, process_id: str) -> bool:
        record = self.get(process_id)
        if record is None or record.terminal:
            return False
        now = self._now()
        with self._connect() as conn:
            if record.status == ProcessStatus.QUEUED:
                conn.execute(
                    "UPDATE processes SET status=?, cancel_requested=1, updated_at=?, finished_at=? WHERE id=?",
                    (ProcessStatus.CANCELLED.value, now, now, process_id),
                )
            else:
                conn.execute(
                    "UPDATE processes SET cancel_requested=1, updated_at=? WHERE id=?", (now, process_id)
                )
        self._emit("process.cancel_requested", process_id=process_id, kind=record.kind)
        return True

    def update_progress(self, process_id: str, progress: float) -> None:
        value = max(0.0, min(1.0, float(progress)))
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE processes SET progress=?, updated_at=? WHERE id=? AND status=?",
                (value, now, process_id, ProcessStatus.RUNNING.value),
            )
        self._emit("process.progress", process_id=process_id, progress=value)

    def recover_interrupted(self) -> int:
        """Requeue processes interrupted by a restart, preserving attempt count."""
        now = self._now()
        recovered: list[tuple[str, str]] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, attempts, max_retries, cancel_requested FROM processes WHERE status=?",
                (ProcessStatus.RUNNING.value,),
            ).fetchall()
            for row in rows:
                if row["cancel_requested"]:
                    status = ProcessStatus.CANCELLED
                    finished = now
                elif int(row["attempts"]) <= int(row["max_retries"]):
                    status = ProcessStatus.QUEUED
                    finished = None
                else:
                    status = ProcessStatus.FAILED
                    finished = now
                conn.execute(
                    "UPDATE processes SET status=?, updated_at=?, finished_at=?, error=? WHERE id=?",
                    (status.value, now, finished, "Interrupted by runtime restart", row["id"]),
                )
                recovered.append((row["id"], status.value))
        for pid, status in recovered:
            self._emit("process.recovered", process_id=pid, status=status)
        return len(recovered)

    def run_next(self) -> ProcessRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM processes WHERE status=? ORDER BY created_at ASC LIMIT 1",
                (ProcessStatus.QUEUED.value,),
            ).fetchone()
        if row is None:
            return None
        return self.run(row["id"])

    def run(self, process_id: str) -> ProcessRecord:
        record = self.get(process_id)
        if record is None:
            raise KeyError(process_id)
        if record.status != ProcessStatus.QUEUED:
            return record
        if record.cancel_requested:
            self.request_cancel(process_id)
            return self.get(process_id)  # type: ignore[return-value]
        handler = self._handlers.get(record.kind)
        if handler is None:
            return self._fail(record, f"No process handler registered for {record.kind}", retry=False)

        now = self._now()
        attempts = record.attempts + 1
        with self._connect() as conn:
            conn.execute(
                "UPDATE processes SET status=?, attempts=?, started_at=COALESCE(started_at, ?), updated_at=?, error=NULL WHERE id=?",
                (ProcessStatus.RUNNING.value, attempts, now, now, process_id),
            )
        self._emit("process.started", process_id=process_id, kind=record.kind, attempt=attempts)
        self._audit("started", process_id, record.kind, metadata={"attempt": attempts})
        deadline = self.clock() + record.timeout_seconds if record.timeout_seconds is not None else None
        context = ProcessContext(self, process_id, deadline)
        try:
            context.checkpoint()
            result = handler(context, record.payload)
            context.checkpoint(1.0)
        except ProcessCancelled as exc:
            return self._finish(record, ProcessStatus.CANCELLED, error=str(exc))
        except ProcessTimedOut as exc:
            return self._finish(record, ProcessStatus.TIMED_OUT, error=str(exc))
        except Exception as exc:
            current = self.get(process_id)
            retry = bool(current and current.attempts <= current.max_retries)
            return self._fail(current or record, f"{type(exc).__name__}: {exc}", retry=retry)
        return self._finish(record, ProcessStatus.SUCCEEDED, result=result)

    def _fail(self, record: ProcessRecord, error: str, *, retry: bool) -> ProcessRecord:
        now = self._now()
        status = ProcessStatus.QUEUED if retry else ProcessStatus.FAILED
        with self._connect() as conn:
            conn.execute(
                "UPDATE processes SET status=?, error=?, updated_at=?, finished_at=? WHERE id=?",
                (status.value, error, now, None if retry else now, record.id),
            )
        event = "process.retry_scheduled" if retry else "process.failed"
        self._emit(event, process_id=record.id, kind=record.kind, error=error)
        self._audit("failed", record.id, record.kind, error=error, metadata={"retry": retry})
        return self.get(record.id)  # type: ignore[return-value]

    def _finish(
        self,
        record: ProcessRecord,
        status: ProcessStatus,
        *,
        result: Any = None,
        error: str | None = None,
    ) -> ProcessRecord:
        now = self._now()
        encoded = None if result is None else json.dumps(result, sort_keys=True, default=str)
        progress = 1.0 if status == ProcessStatus.SUCCEEDED else self.get(record.id).progress  # type: ignore[union-attr]
        with self._connect() as conn:
            conn.execute(
                "UPDATE processes SET status=?, progress=?, result_json=?, error=?, updated_at=?, finished_at=? WHERE id=?",
                (status.value, progress, encoded, error, now, now, record.id),
            )
        self._emit(f"process.{status.value}", process_id=record.id, kind=record.kind, error=error)
        audit_status = "completed" if status == ProcessStatus.SUCCEEDED else status.value
        self._audit(audit_status, record.id, record.kind, result=result, error=error)
        return self.get(record.id)  # type: ignore[return-value]

    def _emit(self, event: str, **payload: Any) -> None:
        if self.event_bus is not None:
            self.event_bus.publish(event, **payload)

    def _audit(self, status: str, process_id: str, kind: str, **kwargs: Any) -> None:
        if self.audit is not None:
            self.audit.record(
                actor_type="process",
                action=kind,
                status=status,
                action_id=process_id,
                **kwargs,
            )
