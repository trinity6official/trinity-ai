import pytest
from core.model_router import LocalModelRouter
from core.models import ChatMessage, ModelInfo, LocalModelNotFoundError

class FakeProvider:
    name = "fake"
    def __init__(self): self.calls=[]
    def health(self): return True
    def available_models(self): return [ModelInfo("small", "fake"), ModelInfo("large", "fake")]
    def chat(self, messages, model=None, **kwargs): self.calls.append(("chat", model)); return f"response:{model}"
    def stream_chat(self, messages, model=None, **kwargs): self.calls.append(("stream", model)); yield "hello"; yield " world"

def router(): return LocalModelRouter([FakeProvider()], {"fast":"small", "general":"small", "reasoning":"large", "coding":"large"})

def test_alias_routes_chat_to_general(): assert router().resolve_model("chat").model == "small"
def test_reasoning_uses_large(): assert router().resolve_model("reasoning").model == "large"
def test_chat_invokes_provider(): assert router().chat([ChatMessage("user","hi")]) == "response:small"
def test_explicit_model_override(): assert router().chat([ChatMessage("user","hi")], model="large") == "response:large"
def test_streaming(): assert "".join(router().stream_chat([ChatMessage("user","hi")])) == "hello world"
def test_health(): assert router().health() == {"fake": True}
def test_unknown_task():
    with pytest.raises(ValueError): router().resolve_model("unknown")


class FallbackProvider(FakeProvider):
    def chat(self, messages, model=None, **kwargs):
        self.calls.append(("chat", model))
        if model == "missing":
            raise LocalModelNotFoundError("not installed")
        return f"response:{model}"


def test_local_model_fallback_uses_second_candidate():
    provider = FallbackProvider()
    r = LocalModelRouter([provider], {"general": ["missing", "small"]})
    assert r.chat([ChatMessage("user", "hi")]) == "response:small"
    assert provider.calls == [("chat", "missing"), ("chat", "small")]


def test_comma_separated_candidates_are_supported():
    r = LocalModelRouter([FakeProvider()], {"general": "small,large"})
    assert r.configured_models("general") == ("small", "large")


class DownProvider(FakeProvider):
    name = "down"
    def health(self):
        return False


class UpProvider(FakeProvider):
    name = "up"


def test_local_model_failover_skips_unhealthy_provider():
    down = DownProvider(); up = UpProvider()
    r = LocalModelRouter([down, up], {"general": "small"})
    assert r.chat([ChatMessage("user", "hi")]) == "response:small"
    assert down.calls == []
    assert up.calls == [("chat", "small")]
