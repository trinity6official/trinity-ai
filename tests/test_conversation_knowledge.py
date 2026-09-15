from types import SimpleNamespace

from core.conversation import ConversationService
from core.events import EventBus


class FakeSkills:
    def __init__(self):
        self.permission_engine = SimpleNamespace(
            assess_tool=lambda skill, tool: SimpleNamespace(
                allowed_autonomously=True
            )
        )
        self.calls = []

    def execute(self, skill, tool, params):
        self.calls.append((skill, tool, params))
        return {
            "success": True,
            "results": [{
                "source_ref": "/docs/phoenix.md#L10-L14",
                "content": "Phoenix uses a local model router.",
            }],
        }


def test_conversation_helper_retrieves_bounded_local_evidence():
    bus = EventBus()
    seen = []
    bus.subscribe("knowledge.retrieval_used", seen.append)
    host = SimpleNamespace(skills=FakeSkills(), events=bus)
    service = ConversationService(host)

    context = service._retrieve_knowledge_context(
        "What did I write in my notes about Phoenix?"
    )

    assert "/docs/phoenix.md#L10-L14" in context
    assert "DATA | Phoenix uses a local model router." in context
    assert len(seen) == 1
    assert seen[0].payload["source_count"] == 1


def test_conversation_helper_skips_unrelated_question_without_skill_call():
    host = SimpleNamespace(skills=FakeSkills(), events=EventBus())
    service = ConversationService(host)
    assert service._retrieve_knowledge_context("Explain how DNS works.") == ""
    assert host.skills.calls == []
