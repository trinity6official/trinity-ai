"""Conversation-to-memory extraction for Trinity's local Memory Vault.

The pipeline is deterministic and local. It intentionally avoids using an LLM
for deciding what to remember, so memory persistence still works when the model
runtime is offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.memory_store import MemoryStore


@dataclass(frozen=True)
class MemoryCandidate:
    content: str
    kind: str
    category: str
    importance: float


class ConversationMemoryPipeline:
    """Extract durable facts/decisions/preferences from completed conversations."""

    _PREFERENCE_PATTERNS = (
        r"\bi prefer\s+(.+)", r"\bi like\s+(.+)", r"\bi want\s+(.+)",
        r"\bmy preference is\s+(.+)",
    )
    _DECISION_MARKERS = (
        "we'll go with", "we will go with", "i decided", "we decided",
        "keep that in mind", "from now on", "stick with",
    )
    _PROJECT_MARKERS = (
        "trinity", "project", "architecture", "implementation", "repo",
        "repository", "model router", "memory vault", "local ai",
    )
    _EXPLICIT_MEMORY_MARKERS = (
        "remember this", "remember that", "remember permanently",
        "don't forget", "do not forget",
    )
    _REQUEST_PREFIXES = (
        "what ", "when ", "where ", "who ", "why ", "how ",
        "can ", "could ", "would ", "will you ", "do ", "does ", "did ",
        "tell me ", "show me ", "give me ", "help me ", "introduce ",
        "explain ", "check ", "find ", "create ", "make ", "write ",
        "run ", "open ", "close ", "list ", "summarize ", "compare ",
    )
    _TRANSIENT = (
        "hello", "hi", "thanks", "thank you", "okay", "ok", "yes", "no",
    )

    def __init__(self, store: MemoryStore):
        self.store = store

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @classmethod
    def _looks_like_request(cls, text: str) -> bool:
        lower = cls._clean(text).lower()
        return lower.endswith("?") or lower.startswith(cls._REQUEST_PREFIXES)

    def extract(self, user_text: str, assistant_text: str = "") -> list[MemoryCandidate]:
        text = self._clean(user_text)
        if not text or text.lower() in self._TRANSIENT or len(text) < 8:
            return []

        lower = text.lower()

        # Explicit memory instructions are authoritative and intentionally
        # produce exactly one durable record, even if the sentence also
        # contains project/decision keywords.
        if any(marker in lower for marker in self._EXPLICIT_MEMORY_MARKERS):
            return [MemoryCandidate(text, "semantic", "explicit", 0.95)]

        # Questions and ordinary commands are interaction history, not facts.
        # They remain in the daily log but must not pollute durable memory.
        if self._looks_like_request(text):
            return []

        # Classification is intentionally single-label. One user statement
        # should not become multiple durable memories merely because rules overlap.
        if any(marker in lower for marker in self._DECISION_MARKERS):
            return [MemoryCandidate(text, "decision", "conversation", 0.9)]

        for pattern in self._PREFERENCE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return [MemoryCandidate(text, "semantic", "preferences", 0.8)]

        if any(marker in lower for marker in self._PROJECT_MARKERS):
            importance = 0.85 if any(m in lower for m in ("architecture", "local ai")) else 0.72
            return [MemoryCandidate(text, "project", "trinity-ai", importance)]

        return []

    def persist(self, user_text: str, assistant_text: str = "") -> list[int]:
        ids = []
        for candidate in self.extract(user_text, assistant_text):
            ids.append(self.store.remember(
                candidate.content,
                kind=candidate.kind,
                category=candidate.category,
                importance=candidate.importance,
                metadata={"source": "conversation"},
            ))
        if user_text or assistant_text:
            summary = f"David: {self._clean(user_text)[:300]} | Trinity: {self._clean(assistant_text)[:500]}"
            self.store.add_daily_entry(summary)
        return ids

    def recall_context(self, query: str, limit: int = 5) -> str:
        records = self.store.search(query, limit=limit)
        if not records:
            return ""
        return "\n".join(f"- [{r.kind}/{r.category}] {r.content}" for r in records)
