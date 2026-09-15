from types import SimpleNamespace

from agents.content_agent import ContentAgent
from core.models import ChatMessage


class FakeLLM:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content="draft")


def test_content_generation_uses_provider_neutral_messages():
    llm = FakeLLM()
    agent = ContentAgent(llm=llm)
    assert agent.generate_linkedin_post("local AI security") == "draft"
    assert all(isinstance(message, ChatMessage) for message in llm.messages)
    assert [message.role for message in llm.messages] == ["system", "user"]


def test_content_delivery_uses_injected_notifier():
    delivered = []
    agent = ContentAgent(notifier=lambda message: delivered.append(message))
    assert agent.deliver_content("linkedin", "hello") is True
    assert delivered == ["LinkedIn Post\n\nhello"]


def test_content_delivery_without_channel_is_nonfatal():
    assert ContentAgent().deliver_content("youtube", "script") is False
