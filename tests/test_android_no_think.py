"""Regression tests for the temporary Android Qwen runtime."""

from types import SimpleNamespace

from core.android_test import AndroidTestRuntime


class FakeRouter:
    def __init__(self):
        self.messages = None
        self.task = None

    def chat(self, messages, task=None):
        self.messages = list(messages)
        self.task = task
        return "hello"


class FakePipeline:
    def recall_context(self, text, limit=5):
        return ""

    def persist(self, text, reply):
        return None


def make_runtime(task):
    runtime = object.__new__(AndroidTestRuntime)

    router = FakeRouter()

    runtime.pipeline = FakePipeline()
    runtime.history = []
    runtime.last_reply = ""
    runtime.stack = SimpleNamespace(
        service=SimpleNamespace(classify_task=lambda text: task),
        router=router,
    )

    return runtime, router


def test_general_chat_disables_qwen_thinking():
    runtime, router = make_runtime("general")

    reply = runtime.ask("hi")

    assert reply == "hello"
    assert router.task == "general"
    assert any(
        message.role == "system" and message.content == "/no_think"
        for message in router.messages
    )


def test_fast_chat_disables_qwen_thinking():
    runtime, router = make_runtime("fast")

    runtime.ask("hello")

    assert any(
        message.role == "system" and message.content == "/no_think"
        for message in router.messages
    )


def test_reasoning_chat_keeps_thinking_enabled():
    runtime, router = make_runtime("reasoning")

    runtime.ask("analyze this architecture")

    assert not any(
        message.role == "system" and message.content == "/no_think"
        for message in router.messages
    )


def test_coding_chat_keeps_thinking_enabled():
    runtime, router = make_runtime("coding")

    runtime.ask("debug this function")

    assert not any(
        message.role == "system" and message.content == "/no_think"
        for message in router.messages
    )
