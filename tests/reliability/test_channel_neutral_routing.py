from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.events import EventBus
from core.message_service import MessageService
from core.orchestrator import MessageOrchestrator
from core.output import ResponseRouter


pytestmark = [pytest.mark.contract, pytest.mark.integration]


def _host():
    bus = EventBus()
    output = ResponseRouter(bus)
    skills = MagicMock()
    skills.get_pending_changes.return_value = {}
    language = MagicMock()
    language.detect_and_respond.return_value = {"language": "english"}
    language.get_response_prefix.return_value = {"thinking": "Thinking..."}
    consciousness = MagicMock()
    host = SimpleNamespace(
        events=bus,
        output=output,
        skills=skills,
        language=language,
        consciousness=consciousness,
        memory=MagicMock(),
        orchestrator=MessageOrchestrator(),
        commands=MagicMock(),
    )
    host.commands.handle.return_value = False
    host.conversation = SimpleNamespace(ask_trinity=MagicMock(return_value="answer"))
    host.respond = lambda message, kind="message": output.emit(message, kind=kind)
    return host


def test_request_responder_receives_all_conversation_output():
    host = _host()
    emitted = []
    result = MessageService(host).handle("hello", responder=emitted.append, source="api")
    assert result == "answer"
    assert emitted == ["Thinking...", "answer"]


def test_response_events_preserve_originating_interface():
    host = _host()
    seen = []
    host.events.subscribe("response.emitted", seen.append)
    MessageService(host).handle("hello", responder=lambda _message: None, source="mobile")
    assert [event.payload["source"] for event in seen] == ["mobile", "mobile"]


def test_command_output_uses_same_bound_responder():
    host = _host()
    host.orchestrator.classify = MagicMock(return_value=SimpleNamespace(kind="command", command="/help"))
    host.commands = SimpleNamespace(handle=lambda command, language: host.respond("help text") or True)
    emitted = []
    MessageService(host).handle("/help", responder=emitted.append, source="api")
    assert emitted == ["help text"]


def test_response_route_does_not_leak_between_requests():
    bus = EventBus()
    default = []
    router = ResponseRouter(bus, default_responder=default.append)
    first = []
    with router.route(first.append, source="api"):
        router.emit("one")
    router.emit("two")
    assert first == ["one"]
    assert default == ["two"]
