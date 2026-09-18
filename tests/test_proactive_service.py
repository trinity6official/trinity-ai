from types import SimpleNamespace
from unittest.mock import MagicMock

from core.events import EventBus
from core.proactive_service import ProactiveService


class Engine:
    def build_prompt(self, **kwargs): return "prompt"
    def parse(self, content):
        return SimpleNamespace(silent=True, skill_requests=[], message=None)


def test_silent_proactive_check_emits_event_without_message(monkeypatch):
    bus = EventBus(); seen=[]; bus.subscribe("proactive.silent", seen.append)
    llm = object()
    host = SimpleNamespace(
        llm=llm, proactive=Engine(), awareness=None, events=bus,
        consciousness=SimpleNamespace(get_context=lambda: "ctx"),
        memory=SimpleNamespace(get_full_context=lambda: "company"),
        respond=MagicMock(),
    )
    host._invoke_with_failover = lambda messages, preferred_llm=None: SimpleNamespace(content="SILENT")
    ProactiveService(host).check()
    assert len(seen) == 1
    host.respond.assert_not_called()


class MessageEngine:
    def build_prompt(self, **kwargs): return "prompt"
    def parse(self, content):
        return SimpleNamespace(silent=False, skill_requests=[], message="Important update")


def test_duplicate_proactive_message_is_suppressed():
    bus = EventBus(); suppressed=[]; bus.subscribe("proactive.suppressed", suppressed.append)
    host = SimpleNamespace(
        llm=object(), proactive=MessageEngine(), awareness=None, events=bus,
        consciousness=SimpleNamespace(get_context=lambda: "ctx", remember=lambda *a, **k: None),
        memory=SimpleNamespace(get_full_context=lambda: "company"),
        permissions=SimpleNamespace(assess_action=lambda action: SimpleNamespace(allowed_autonomously=True)),
        notify=MagicMock(), respond=MagicMock(),
    )
    host._invoke_with_failover = lambda *a, **k: SimpleNamespace(content="Important update")
    times=iter([100.0, 101.0])
    service=ProactiveService(host, clock=lambda: next(times))
    service.check(); service.check()
    assert host.notify.call_count == 1
    assert len(suppressed) == 1


def test_proactive_skill_gap_requests_approval_instead_of_self_modifying():
    bus = EventBus(); seen=[]; bus.subscribe("proactive.skill_approval_required", seen.append)
    class GapEngine:
        def build_prompt(self, **kwargs): return "prompt"
        def parse(self, content):
            return SimpleNamespace(
                silent=False,
                skill_requests=[SimpleNamespace(name="email_agent", reason="Need inbox triage")],
                message=None,
            )
    host = SimpleNamespace(
        llm=object(), proactive=GapEngine(), awareness=None, events=bus,
        consciousness=SimpleNamespace(get_context=lambda: "ctx"),
        memory=SimpleNamespace(get_full_context=lambda: "company"),
        respond=MagicMock(),
    )
    host._invoke_with_failover = lambda messages, preferred_llm=None: SimpleNamespace(content="gap")
    ProactiveService(host).check()
    assert len(seen) == 1
    assert seen[0].payload["skill"] == "email_agent"
