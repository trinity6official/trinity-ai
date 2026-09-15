from types import SimpleNamespace

from core.android_test import AndroidTestRuntime


class FakeRouter:
    def chat(self, messages, task="general"):
        assert any(m.role == "user" for m in messages)
        return "Hello from local Trinity"


class FakeService:
    def classify_task(self, text):
        return "general"


def test_android_runtime_uses_real_memory_pipeline(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "android_test.yaml").write_text("local_ai: {}", encoding="utf-8")
    fake = SimpleNamespace(
        router=FakeRouter(), service=FakeService(), provider_available=True,
        provider_name="llama_cpp", base_url="http://127.0.0.1:8080",
        general_model_name="trinity-phone",
    )
    monkeypatch.setattr("core.android_test.build_local_ai_from_environment", lambda env: fake)
    monkeypatch.setattr("core.android_test.LocalVoiceService", lambda: SimpleNamespace())
    runtime = AndroidTestRuntime(tmp_path)
    reply = runtime.ask("Remember that this phone is my temporary Trinity test device")
    assert reply == "Hello from local Trinity"
    assert runtime.memory.search("temporary Trinity test device")


def test_android_runtime_injects_recalled_memory(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "android_test.yaml").write_text("local_ai: {}", encoding="utf-8")
    seen = {}
    class Router:
        def chat(self, messages, task="general"):
            seen["messages"] = messages
            return "remembered"
    fake = SimpleNamespace(
        router=Router(), service=FakeService(), provider_available=True,
        provider_name="llama_cpp", base_url="http://127.0.0.1:8080",
        general_model_name="trinity-phone",
    )
    monkeypatch.setattr("core.android_test.build_local_ai_from_environment", lambda env: fake)
    monkeypatch.setattr("core.android_test.LocalVoiceService", lambda: SimpleNamespace())
    runtime = AndroidTestRuntime(tmp_path)
    runtime.memory.remember("Phone is temporary", category="explicit", importance=0.9)
    runtime.ask("What is temporary?")
    assert any("Phone is temporary" in m.content for m in seen["messages"])
