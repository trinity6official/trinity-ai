from types import SimpleNamespace

from core.api_bridge import ask_runtime, runtime_capabilities


class FakeMessages:
    def __init__(self): self.calls=[]
    def handle(self, text, chat_id, responder=None, source=None):
        self.calls.append((text, chat_id, source))
        responder("Thinking")
        responder("Full Trinity response")
        return "Full Trinity response"


class FakeRuntime:
    def __init__(self):
        self.messages = FakeMessages()
        self.vision = SimpleNamespace(available=lambda: False)
        self.model_router = SimpleNamespace(health=lambda: {"local": True})
        self.computer = SimpleNamespace(provider=None)
        self.telegram = SimpleNamespace(enabled=True)
        self.memory_store = object()


def test_api_bridge_uses_full_runtime_message_pipeline():
    runtime = FakeRuntime()
    assert ask_runtime(runtime, "hello") == "Full Trinity response"
    assert runtime.messages.calls == [("hello", None, "api")]
    caps = runtime_capabilities(runtime)
    assert caps["runtime_bound"] is True
    assert caps["local_ai"] is True


def test_api_bridge_compatibility_fallback_still_uses_bound_runtime_object():
    brain = SimpleNamespace(ask_trinity=lambda text: f"bound:{text}")
    assert ask_runtime(brain, "hello") == "bound:hello"
