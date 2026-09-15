"""Message intent routing for Trinity.

This module is intentionally side-effect free. It decides what a message means;
execution remains in command/agent layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MessageKind(str, Enum):
    APPROVAL = "approval"
    REJECTION = "rejection"
    COMMAND = "command"
    CONVERSATION = "conversation"


@dataclass(frozen=True)
class MessageIntent:
    kind: MessageKind
    text: str
    command: str | None = None


class MessageOrchestrator:
    APPROVAL_WORDS = {
        "YES", "GO AHEAD", "CONFIRM", "APPROVE", "DO IT", "ஆம்", "சரி"
    }
    REJECTION_WORDS = {"NO", "CANCEL", "REJECT", "STOP", "வேண்டாம்"}

    def classify(self, text: str, *, has_pending_change: bool = False) -> MessageIntent:
        clean = (text or "").strip()
        upper = clean.upper()

        if has_pending_change and upper in self.APPROVAL_WORDS:
            return MessageIntent(MessageKind.APPROVAL, clean)
        if has_pending_change and upper in self.REJECTION_WORDS:
            return MessageIntent(MessageKind.REJECTION, clean)
        if clean.startswith("/"):
            return MessageIntent(MessageKind.COMMAND, clean, command=clean.split()[0].lower())
        return MessageIntent(MessageKind.CONVERSATION, clean)
