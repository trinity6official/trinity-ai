"""Small testable scheduler for Trinity's always-on runtime."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from core.events import EventBus


Callback = Callable[[], object]


@dataclass
class IntervalTask:
    name: str
    every_seconds: float
    callback: Callback
    last_run_at: float


@dataclass
class DailyTask:
    name: str
    hour: int
    minute: int
    callback: Callback
    last_run_date: date | None = None


class RuntimeScheduler:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus
        self.interval_tasks: list[IntervalTask] = []
        self.daily_tasks: list[DailyTask] = []

    def add_interval(self, name: str, every_seconds: float, callback: Callback, *, now_seconds: float) -> None:
        self.interval_tasks.append(IntervalTask(name, every_seconds, callback, now_seconds))

    def add_daily(
        self,
        name: str,
        hour: int,
        minute: int,
        callback: Callback,
        *,
        last_run_date: date | None = None,
    ) -> None:
        self.daily_tasks.append(DailyTask(name, hour, minute, callback, last_run_date))

    def _run(self, name: str, callback: Callback) -> None:
        if self.event_bus is not None:
            self.event_bus.publish("scheduler.task_started", task=name)
        try:
            callback()
            if self.event_bus is not None:
                self.event_bus.publish("scheduler.task_completed", task=name)
        except Exception as exc:
            if self.event_bus is not None:
                self.event_bus.publish("scheduler.task_failed", task=name, error=str(exc))

    def tick(self, *, current: datetime, now_seconds: float) -> None:
        for task in self.interval_tasks:
            if now_seconds - task.last_run_at >= task.every_seconds:
                task.last_run_at = now_seconds
                self._run(task.name, task.callback)

        for task in self.daily_tasks:
            due_time = (current.hour, current.minute) >= (task.hour, task.minute)
            if due_time and task.last_run_date != current.date():
                task.last_run_date = current.date()
                self._run(task.name, task.callback)
