from types import SimpleNamespace

from core.run import resolve_mode, run_runtime
from core.runtime import RuntimeMode


class FakeEvents:
    def __init__(self):
        self.events = []

    def publish(self, name, **payload):
        self.events.append((name, payload))


class FakeTrinity:
    def __init__(self):
        self.events = FakeEvents()
        self.runtime_mode = None
        self.run_calls = 0
        self.shutdown_calls = 0

    def run(self):
        self.run_calls += 1

    def _shutdown(self):
        self.shutdown_calls += 1


def test_resolve_mode_keeps_actions_only_as_ci_alias(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert resolve_mode("auto") == RuntimeMode.CI
    assert resolve_mode("actions") == RuntimeMode.CI
    assert resolve_mode("daemon") == RuntimeMode.LOCAL_DAEMON
    assert resolve_mode("oneshot") == RuntimeMode.LOCAL_ONESHOT


def test_daemon_uses_modern_trinity_runtime():
    runtime = FakeTrinity()
    assert run_runtime(RuntimeMode.LOCAL_DAEMON, trinity_factory=lambda: runtime) == 0
    assert runtime.runtime_mode == RuntimeMode.LOCAL_DAEMON
    assert runtime.run_calls == 1
    assert runtime.shutdown_calls == 0


def test_ci_boot_validation_never_enters_daemon_loop():
    runtime = FakeTrinity()
    assert run_runtime(RuntimeMode.CI, trinity_factory=lambda: runtime) == 0
    assert runtime.runtime_mode == RuntimeMode.CI
    assert runtime.run_calls == 0
    assert runtime.shutdown_calls == 1
    assert runtime.events.events == [("runtime.oneshot", {"mode": "ci"})]


def test_local_oneshot_uses_normal_shutdown_path():
    runtime = FakeTrinity()
    run_runtime(RuntimeMode.LOCAL_ONESHOT, trinity_factory=lambda: runtime)
    assert runtime.shutdown_calls == 1
    assert runtime.events.events[-1][1]["mode"] == "local_oneshot"
