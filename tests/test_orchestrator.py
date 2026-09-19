from core.orchestrator import MessageKind, MessageOrchestrator


def test_yes_is_approval_only_when_change_pending():
    router = MessageOrchestrator()
    assert router.classify("yes", has_pending_change=True).kind == MessageKind.APPROVAL
    assert router.classify("yes", has_pending_change=False).kind == MessageKind.CONVERSATION


def test_no_is_rejection_only_when_change_pending():
    router = MessageOrchestrator()
    assert router.classify("NO", has_pending_change=True).kind == MessageKind.REJECTION
    assert router.classify("NO", has_pending_change=False).kind == MessageKind.CONVERSATION


def test_tamil_approval_supported():
    assert MessageOrchestrator().classify("ஆம்", has_pending_change=True).kind == MessageKind.APPROVAL


def test_command_is_normalized():
    intent = MessageOrchestrator().classify(" /STATUS ")
    assert intent.kind == MessageKind.COMMAND
    assert intent.command == "/status"


def test_plain_text_is_conversation():
    intent = MessageOrchestrator().classify("analyze the architecture")
    assert intent.kind == MessageKind.CONVERSATION

def test_targeted_approval_carries_pending_id():
    intent = MessageOrchestrator().classify(
        "APPROVE abc123",
        has_pending_change=True,
    )
    assert intent.kind == MessageKind.APPROVAL
    assert intent.approval_id == "abc123"


def test_targeted_rejection_carries_pending_id():
    intent = MessageOrchestrator().classify(
        "REJECT abc123",
        has_pending_change=True,
    )
    assert intent.kind == MessageKind.REJECTION
    assert intent.approval_id == "abc123"


def test_targeted_approval_is_plain_conversation_without_pending_items():
    intent = MessageOrchestrator().classify(
        "APPROVE abc123",
        has_pending_change=False,
    )
    assert intent.kind == MessageKind.CONVERSATION
