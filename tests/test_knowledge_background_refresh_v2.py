from datetime import datetime
from types import SimpleNamespace

from core.lifecycle import RuntimeLoop
from core.process_manager import ProcessManager


class FakeSkills:
    def __init__(self):
        self.calls = []

    def execute(self, skill, tool, params):
        self.calls.append((skill, tool, params))
        return {"success": True, "updated": 0}


def _host(tmp_path, skills):
    return SimpleNamespace(
        events=None,
        processes=ProcessManager(tmp_path / "processes.db"),
        skills=skills,
        briefings=SimpleNamespace(deliver_morning=lambda: None),
        proactive_service=SimpleNamespace(check=lambda: None),
        perception=None,
    )


def test_scheduler_adds_incremental_knowledge_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("TRINITY_KNOWLEDGE_REFRESH_INTERVAL_SECONDS", "900")
    skills = FakeSkills()
    host = _host(tmp_path, skills)
    loop = RuntimeLoop(
        host,
        now=lambda: datetime(2026, 9, 15, 12, 0, 0),
        scheduler_path=str(tmp_path / "schedules.db"),
    )

    scheduler = loop._build_scheduler()
    assert "knowledge_refresh" in [task.name for task in scheduler.list(enabled=True)]

    scheduler.tick(current=datetime(2026, 9, 15, 12, 15, 0))
    while host.processes.run_next() is not None:
        pass
    assert ("knowledge", "refresh_knowledge_index", {}) in skills.calls


def test_scheduler_can_disable_knowledge_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED", "false")
    host = _host(tmp_path, FakeSkills())
    scheduler = RuntimeLoop(
        host,
        now=lambda: datetime(2026, 9, 15, 12, 0, 0),
        scheduler_path=str(tmp_path / "schedules.db"),
    )._build_scheduler()
    assert "knowledge_refresh" not in [task.name for task in scheduler.list(enabled=True)]
