"""Persistent schedule store that submits due work into ProcessManager."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from core.events import EventBus
from core.execution import freeze_mapping, thaw_mapping
from core.process_manager import ProcessManager, ProcessRecord


class ScheduleKind(str, Enum):
    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"


@dataclass(frozen=True)
class ScheduleRecord:
    id: str
    name: str
    kind: ScheduleKind
    process_kind: str
    payload: Mapping[str, Any]
    next_run_at: datetime
    interval_seconds: float | None
    daily_hour: int | None
    daily_minute: int | None
    max_retries: int
    timeout_seconds: float | None
    enabled: bool
    last_run_at: datetime | None
    last_process_id: str | None
    created_at: str
    updated_at: str


class PersistentScheduler:
    """Persist schedules and submit each due occurrence exactly once.

    Execution is intentionally delegated to ``ProcessManager``. Deterministic
    process IDs make schedule submission crash-safe: if Trinity restarts after a
    process was inserted but before the schedule advances, the same occurrence
    is recognized instead of being inserted twice.
    """

    def __init__(
        self,
        process_manager: ProcessManager,
        path: str | Path = "memory/runtime/schedules.db",
        *,
        event_bus: EventBus | None = None,
    ) -> None:
        self.processes = process_manager
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self._initialize()

    @staticmethod
    def _stamp(value: datetime) -> str:
        return value.isoformat(timespec="microseconds")

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    process_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    next_run_at TEXT NOT NULL,
                    interval_seconds REAL,
                    daily_hour INTEGER,
                    daily_minute INTEGER,
                    max_retries INTEGER NOT NULL DEFAULT 0,
                    timeout_seconds REAL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT,
                    last_process_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_schedule_due ON schedules(enabled, next_run_at)"
            )

    def _row(self, row: sqlite3.Row) -> ScheduleRecord:
        return ScheduleRecord(
            id=row["id"],
            name=row["name"],
            kind=ScheduleKind(row["kind"]),
            process_kind=row["process_kind"],
            payload=freeze_mapping(json.loads(row["payload_json"])),
            next_run_at=datetime.fromisoformat(row["next_run_at"]),
            interval_seconds=row["interval_seconds"],
            daily_hour=row["daily_hour"],
            daily_minute=row["daily_minute"],
            max_retries=int(row["max_retries"]),
            timeout_seconds=row["timeout_seconds"],
            enabled=bool(row["enabled"]),
            last_run_at=self._parse(row["last_run_at"]),
            last_process_id=row["last_process_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get(self, name: str) -> ScheduleRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE name=?", (name,)).fetchone()
        return self._row(row) if row else None

    def list(self, *, enabled: bool | None = None) -> list[ScheduleRecord]:
        with self._connect() as conn:
            if enabled is None:
                rows = conn.execute("SELECT * FROM schedules ORDER BY name").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM schedules WHERE enabled=? ORDER BY name",
                    (1 if enabled else 0,),
                ).fetchall()
        return [self._row(row) for row in rows]

    def _ensure(
        self,
        *,
        name: str,
        kind: ScheduleKind,
        process_kind: str,
        payload: Mapping[str, Any] | None,
        next_run_at: datetime,
        interval_seconds: float | None,
        daily_hour: int | None,
        daily_minute: int | None,
        max_retries: int,
        timeout_seconds: float | None,
    ) -> ScheduleRecord:
        name = str(name).strip()
        process_kind = str(process_kind).strip()
        if not name or not process_kind:
            raise ValueError("Schedule name and process kind are required")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        frozen = freeze_mapping(payload)
        payload_json = json.dumps(thaw_mapping(frozen), sort_keys=True)
        current = self.get(name)
        now = datetime.now().isoformat(timespec="microseconds")
        if current is None:
            schedule_id = uuid4().hex
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO schedules (
                        id, name, kind, process_kind, payload_json, next_run_at,
                        interval_seconds, daily_hour, daily_minute, max_retries,
                        timeout_seconds, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        schedule_id,
                        name,
                        kind.value,
                        process_kind,
                        payload_json,
                        self._stamp(next_run_at),
                        interval_seconds,
                        daily_hour,
                        daily_minute,
                        max_retries,
                        timeout_seconds,
                        now,
                        now,
                    ),
                )
            return self.get(name)  # type: ignore[return-value]

        same_contract = (
            current.kind == kind
            and current.process_kind == process_kind
            and thaw_mapping(current.payload) == thaw_mapping(frozen)
            and current.interval_seconds == interval_seconds
            and current.daily_hour == daily_hour
            and current.daily_minute == daily_minute
            and current.max_retries == max_retries
            and current.timeout_seconds == timeout_seconds
            and (kind != ScheduleKind.ONCE or current.next_run_at == next_run_at)
        )
        if same_contract:
            if not current.enabled and kind != ScheduleKind.ONCE:
                self.resume(name)
                return self.get(name)  # type: ignore[return-value]
            return current

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE schedules
                SET kind=?, process_kind=?, payload_json=?, next_run_at=?,
                    interval_seconds=?, daily_hour=?, daily_minute=?, max_retries=?,
                    timeout_seconds=?, enabled=1, last_run_at=NULL,
                    last_process_id=NULL, updated_at=?
                WHERE name=?
                """,
                (
                    kind.value,
                    process_kind,
                    payload_json,
                    self._stamp(next_run_at),
                    interval_seconds,
                    daily_hour,
                    daily_minute,
                    max_retries,
                    timeout_seconds,
                    now,
                    name,
                ),
            )
        return self.get(name)  # type: ignore[return-value]

    def add_once(
        self,
        name: str,
        run_at: datetime,
        process_kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        max_retries: int = 0,
        timeout_seconds: float | None = None,
    ) -> ScheduleRecord:
        return self._ensure(
            name=name,
            kind=ScheduleKind.ONCE,
            process_kind=process_kind,
            payload=payload,
            next_run_at=run_at,
            interval_seconds=None,
            daily_hour=None,
            daily_minute=None,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    def add_interval(
        self,
        name: str,
        every_seconds: float,
        process_kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        start_at: datetime,
        max_retries: int = 0,
        timeout_seconds: float | None = None,
    ) -> ScheduleRecord:
        every_seconds = float(every_seconds)
        if every_seconds <= 0:
            raise ValueError("every_seconds must be positive")
        return self._ensure(
            name=name,
            kind=ScheduleKind.INTERVAL,
            process_kind=process_kind,
            payload=payload,
            next_run_at=start_at + timedelta(seconds=every_seconds),
            interval_seconds=every_seconds,
            daily_hour=None,
            daily_minute=None,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    def add_daily(
        self,
        name: str,
        hour: int,
        minute: int,
        process_kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        start_at: datetime,
        max_retries: int = 0,
        timeout_seconds: float | None = None,
    ) -> ScheduleRecord:
        if not 0 <= int(hour) <= 23 or not 0 <= int(minute) <= 59:
            raise ValueError("Invalid daily schedule time")
        candidate = start_at.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        # If today's time already passed, keep it due now on first creation. A
        # persisted schedule will already point to the next day after it runs.
        return self._ensure(
            name=name,
            kind=ScheduleKind.DAILY,
            process_kind=process_kind,
            payload=payload,
            next_run_at=candidate,
            interval_seconds=None,
            daily_hour=int(hour),
            daily_minute=int(minute),
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    def pause(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE schedules SET enabled=0, updated_at=? WHERE name=?",
                (datetime.now().isoformat(timespec="microseconds"), name),
            )

    def resume(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE schedules SET enabled=1, updated_at=? WHERE name=?",
                (datetime.now().isoformat(timespec="microseconds"), name),
            )

    def delete(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM schedules WHERE name=?", (name,))

    @staticmethod
    def _process_id(schedule: ScheduleRecord) -> str:
        key = f"{schedule.id}|{schedule.next_run_at.isoformat()}".encode("utf-8")
        return "sched-" + hashlib.sha256(key).hexdigest()[:24]

    @staticmethod
    def _next_due(schedule: ScheduleRecord, current: datetime) -> datetime | None:
        if schedule.kind == ScheduleKind.ONCE:
            return None
        if schedule.kind == ScheduleKind.INTERVAL:
            assert schedule.interval_seconds is not None
            elapsed = max(0.0, (current - schedule.next_run_at).total_seconds())
            steps = int(elapsed // schedule.interval_seconds) + 1
            return schedule.next_run_at + timedelta(
                seconds=steps * schedule.interval_seconds
            )
        assert schedule.daily_hour is not None and schedule.daily_minute is not None
        next_day = (current + timedelta(days=1)).date()
        return datetime.combine(next_day, datetime.min.time()).replace(
            hour=schedule.daily_hour, minute=schedule.daily_minute
        )

    def tick(self, *, current: datetime) -> list[ProcessRecord]:
        due = [
            schedule
            for schedule in self.list(enabled=True)
            if schedule.next_run_at <= current
        ]
        submitted: list[ProcessRecord] = []
        for schedule in sorted(due, key=lambda item: item.next_run_at):
            process_id = self._process_id(schedule)
            process = self.processes.get(process_id)
            if process is None:
                process = self.processes.submit(
                    schedule.process_kind,
                    schedule.payload,
                    max_retries=schedule.max_retries,
                    timeout_seconds=schedule.timeout_seconds,
                    process_id=process_id,
                )
                submitted.append(process)
                if self.event_bus is not None:
                    self.event_bus.publish(
                        "scheduler.task_submitted",
                        task=schedule.name,
                        schedule_id=schedule.id,
                        process_id=process_id,
                    )

            next_due = self._next_due(schedule, current)
            now = datetime.now().isoformat(timespec="microseconds")
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE schedules
                    SET next_run_at=?, enabled=?, last_run_at=?, last_process_id=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        self._stamp(next_due or schedule.next_run_at),
                        0 if next_due is None else 1,
                        self._stamp(schedule.next_run_at),
                        process_id,
                        now,
                        schedule.id,
                    ),
                )
        return submitted
