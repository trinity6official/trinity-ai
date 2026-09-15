from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.ai_service import LocalAIService


def make_service():
    router = MagicMock()
    router.model.side_effect = lambda task: SimpleNamespace(task=task, invoke=lambda messages: "ok")
    return LocalAIService(router), router


def test_general_query_classification():
    service, _ = make_service()
    assert service.classify_task("What is the website status?") == "general"


def test_code_query_classification():
    service, _ = make_service()
    assert service.classify_task("refactor this Python function") == "coding"


def test_code_block_classification():
    service, _ = make_service()
    assert service.classify_task("help\n```python\npass\n```") == "coding"


def test_reasoning_query_classification():
    service, _ = make_service()
    assert service.classify_task("analyze the architecture") == "reasoning"


def test_long_query_classification():
    service, _ = make_service()
    assert service.classify_task("x " * 150) == "reasoning"


def test_model_for_uses_router():
    service, router = make_service()
    model = service.model_for("debug this code")
    assert model.task == "coding"
    router.model.assert_called_with("coding")


def test_invoke_wraps_local_error():
    service, router = make_service()
    broken = MagicMock()
    broken.invoke.side_effect = ValueError("boom")
    with pytest.raises(RuntimeError, match="Local AI invocation failed"):
        service.invoke([], model=broken)


def test_build_local_ai_from_environment_uses_configured_models(monkeypatch):
    from core import ai_service

    class FakeProvider:
        name = "ollama"
        def __init__(self, base_url): self.base_url = base_url
        def health(self): return True
        def available_models(self): return []
        def chat(self, messages, model=None, **kwargs): return "ok"
        def stream_chat(self, messages, model=None, **kwargs): yield "ok"

    monkeypatch.setattr(ai_service, "OllamaProvider", FakeProvider)
    stack = ai_service.build_local_ai_from_environment({
        "LOCAL_LLM_URL": "http://local:11434",
        "TRINITY_GENERAL_MODEL": "general-local",
        "TRINITY_FAST_MODEL": "fast-local",
        "TRINITY_REASONING_MODEL": "reason-local",
        "TRINITY_CODING_MODEL": "code-local",
    })
    assert stack.base_url == "http://local:11434"
    assert stack.general_model_name == "general-local"
    assert stack.ollama_available is True
    assert stack.router.configured_models("coding") == ("code-local",)


def test_build_local_ai_uses_yaml_defaults_with_environment_override(tmp_path, monkeypatch):
    from core import ai_service

    config = tmp_path / "local_ai.yaml"
    config.write_text(
        """local_ai:
  provider: ollama
  base_url: http://yaml-host:11434
  tasks:
    fast: [yaml-fast, yaml-fast-backup]
    general: [yaml-general, yaml-general-backup]
    reasoning: yaml-reason
    coding: yaml-code
"""
    )

    class FakeProvider:
        name = "ollama"
        def __init__(self, base_url): self.base_url = base_url
        def health(self): return True
        def available_models(self): return []
        def chat(self, messages, model=None, **kwargs): return "ok"
        def stream_chat(self, messages, model=None, **kwargs): yield "ok"

    monkeypatch.setattr(ai_service, "OllamaProvider", FakeProvider)
    stack = ai_service.build_local_ai_from_environment({
        "TRINITY_LOCAL_AI_CONFIG": str(config),
        "TRINITY_CODING_MODEL": "env-code",
    })
    assert stack.base_url == "http://yaml-host:11434"
    assert stack.general_model_name == "yaml-general"
    assert stack.router.configured_models("fast") == ("yaml-fast", "yaml-fast-backup")
    assert stack.router.configured_models("coding") == ("env-code",)


def test_build_local_ai_supports_llama_cpp_profile(tmp_path, monkeypatch):
    from core import ai_service

    config = tmp_path / "android.yaml"
    config.write_text("""local_ai:
  provider: llama_cpp
  base_url: http://127.0.0.1:8080
  tasks:
    fast: trinity-phone
    general: trinity-phone
    reasoning: trinity-phone
    coding: trinity-phone
""")

    class FakeLlamaCpp:
        name = "llama_cpp"
        def __init__(self, base_url): self.base_url = base_url
        def health(self): return True
        def available_models(self): return []
        def chat(self, messages, model=None, **kwargs): return "ok"
        def stream_chat(self, messages, model=None, **kwargs): yield "ok"

    monkeypatch.setattr(ai_service, "LlamaCppProvider", FakeLlamaCpp)
    stack = ai_service.build_local_ai_from_environment({"TRINITY_LOCAL_AI_CONFIG": str(config)})
    assert stack.provider_name == "llama_cpp"
    assert stack.provider_available is True
    assert stack.ollama_available is False
    assert stack.general_model_name == "trinity-phone"
