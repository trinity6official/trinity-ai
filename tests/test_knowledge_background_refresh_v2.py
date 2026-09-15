from datetime import datetime
from types import SimpleNamespace

from core.lifecycle import RuntimeLoop


class FakeSkills:
    def __init__(self):
        self.calls = []

    def execute(self, skill, tool, params):
        self.calls.append((skill, tool, params))
        return {"success": True, "updated": 0}


def test_scheduler_adds_incremental_knowledge_refresh(monkeypatch):
    monkeypatch.setenv("TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("TRINITY_KNOWLEDGE_REFRESH_INTERVAL_SECONDS", "900")
    skills = FakeSkills()
    host = SimpleNamespace(
        events=None,
        skills=skills,
        deliver_morning_briefing=lambda: None,
        _proactive_initiative_check=lambda: None,
        perception=None,
    )
    loop = RuntimeLoop(
        host,
        clock=lambda: 0.0,
        now=lambda: datetime(2026, 9, 15, 12, 0, 0),
    )

    scheduler = loop._build_scheduler()
    names = [task.name for task in scheduler.interval_tasks]
    assert "knowledge_refresh" in names

    scheduler.tick(current=datetime(2026, 9, 15, 12, 15, 0), now_seconds=901.0)
    assert ("knowledge", "refresh_knowledge_index", {}) in skills.calls


def test_scheduler_can_disable_knowledge_refresh(monkeypatch):
    monkeypatch.setenv("TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED", "false")
    host = SimpleNamespace(
        events=None,
        skills=FakeSkills(),
        deliver_morning_briefing=lambda: None,
        _proactive_initiative_check=lambda: None,
        perception=None,
    )
    scheduler = RuntimeLoop(host, clock=lambda: 0.0)._build_scheduler()
    assert "knowledge_refresh" not in [task.name for task in scheduler.interval_tasks]
