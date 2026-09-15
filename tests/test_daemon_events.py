from pathlib import Path
from types import SimpleNamespace

from core.daemon import DaemonMode
from core.events import EventBus


class Consciousness:
    def __init__(self, root: Path):
        self.brain_path = root / "brain.json"
        self.brain_path.write_text("{}")
        self.brain = {
            "state": {"energy": 0.8, "confidence": 0.7},
            "working": [], "operations_log": [], "patterns": [],
        }
    def get_memory_stats(self):
        return {"episodic_count": 451, "operations_logged": 0}
    def add_working(self, *args, **kwargs): pass
    def save(self): pass


def test_daemon_health_warning_emits_event(tmp_path):
    bus = EventBus(); seen = []; bus.subscribe("health.warning", seen.append)
    consciousness = Consciousness(tmp_path)
    host = SimpleNamespace(consciousness=consciousness, events=bus)
    daemon = DaemonMode(host, on_health_warning=lambda warnings: None)
    daemon._health_check()
    assert len(seen) == 1
    assert "approaching limit" in seen[0].payload["message"]


def test_daemon_has_no_git_persistence_capability(tmp_path):
    host = SimpleNamespace(consciousness=Consciousness(tmp_path), events=EventBus())
    daemon = DaemonMode(host)
    assert not hasattr(daemon, "git_commit")
    assert not hasattr(daemon, "_git_commit")
    assert "total_git_commits" not in daemon.get_daemon_stats()
