"""Automatic retrieval policy for Trinity's approved local knowledge.

The retrieval path is deterministic and intentionally cheap. It does not call an
LLM. It only searches the local knowledge index when the user's wording suggests
that personal files/notes are likely to contain relevant evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class KnowledgeRetrievalDecision:
    retrieve: bool
    reason: str


@dataclass(frozen=True)
class KnowledgeRetrievalContext:
    used: bool
    reason: str
    context: str = ""
    source_refs: tuple[str, ...] = ()


class KnowledgeRetrievalPolicy:
    """Deterministic router for deciding when local knowledge is relevant."""

    _EXPLICIT_PHRASES = (
        "my notes", "our notes", "my document", "our document",
        "my docs", "our docs", "my file", "our file",
        "from my files", "from our files", "personal knowledge",
        "knowledge base", "local notes", "local document", "local file",
        "i wrote", "we wrote", "i documented", "we documented",
    )
    _PERSONAL_TERMS = {"my", "our", "we", "i"}
    _ARTIFACT_TERMS = {
        "notes", "note", "document", "documents", "docs", "file", "files",
        "readme", "runbook", "spec", "specification", "proposal", "report",
        "standard", "policy", "procedure", "architecture", "design", "plan",
        "project",
    }
    _RECALL_TERMS = {
        "wrote", "write", "documented", "noted", "mention", "mentioned",
        "say", "said", "defined", "designed", "saved", "according",
    }
    _CURRENT_ONLY_TERMS = {
        "today", "latest", "current", "currently", "news", "weather",
        "stock", "price", "score", "breaking", "now",
    }
    _MANAGEMENT_PHRASES = (
        "index this", "index folder", "index directory",
        "add knowledge root", "refresh knowledge", "refresh the knowledge",
        "remove knowledge root",
    )
    _PATH_RE = re.compile(
        r"(?:[/\\~][^\s]+)|(?:\b[\w.-]+\.(?:md|txt|rst|json|ya?ml|toml|csv|py|sh|go|rb|js|ts|sql)\b)",
        re.IGNORECASE,
    )
    _WORD_RE = re.compile(r"[A-Za-z0-9_.-]+")

    def decide(self, question: str) -> KnowledgeRetrievalDecision:
        raw = str(question or "").strip()
        q = raw.lower()
        if not q:
            return KnowledgeRetrievalDecision(False, "empty")

        if any(phrase in q for phrase in self._MANAGEMENT_PHRASES):
            return KnowledgeRetrievalDecision(False, "knowledge_management_request")

        if any(phrase in q for phrase in self._EXPLICIT_PHRASES):
            return KnowledgeRetrievalDecision(True, "explicit_personal_knowledge_cue")

        if self._PATH_RE.search(raw):
            return KnowledgeRetrievalDecision(True, "local_path_or_filename")

        tokens = {token.lower() for token in self._WORD_RE.findall(raw)}
        if len(tokens) < 3:
            return KnowledgeRetrievalDecision(False, "too_short")

        personal = bool(tokens & self._PERSONAL_TERMS)
        artifact = bool(tokens & self._ARTIFACT_TERMS)
        recall = bool(tokens & self._RECALL_TERMS)

        if personal and artifact:
            return KnowledgeRetrievalDecision(True, "personal_artifact_cue")

        if artifact and recall:
            return KnowledgeRetrievalDecision(True, "artifact_recall_cue")

        if tokens & self._CURRENT_ONLY_TERMS:
            return KnowledgeRetrievalDecision(False, "current_information_query")

        return KnowledgeRetrievalDecision(False, "no_local_knowledge_cue")


class KnowledgeRetrievalService:
    """Search approved local knowledge and format bounded source-backed evidence."""

    def __init__(
        self,
        *,
        policy: KnowledgeRetrievalPolicy | None = None,
        max_results: int = 3,
        max_chunk_chars: int = 1100,
        max_context_chars: int = 3600,
    ) -> None:
        self.policy = policy or KnowledgeRetrievalPolicy()
        self.max_results = max(1, min(int(max_results), 5))
        self.max_chunk_chars = max(200, int(max_chunk_chars))
        self.max_context_chars = max(600, int(max_context_chars))

    def retrieve(
        self,
        question: str,
        skill_manager: Any,
    ) -> KnowledgeRetrievalContext:
        decision = self.policy.decide(question)
        if not decision.retrieve:
            return KnowledgeRetrievalContext(False, decision.reason)

        permission_engine = getattr(skill_manager, "permission_engine", None)
        if permission_engine is not None:
            permission = permission_engine.assess_tool(
                "knowledge", "search_knowledge"
            )
            if not permission.allowed_autonomously:
                return KnowledgeRetrievalContext(False, "permission_not_autonomous")

        result = skill_manager.execute(
            "knowledge",
            "search_knowledge",
            {"query": str(question), "limit": self.max_results},
        )
        if not isinstance(result, dict) or not result.get("success", False):
            return KnowledgeRetrievalContext(False, "knowledge_search_failed")

        rows = result.get("results")
        if not isinstance(rows, list) or not rows:
            return KnowledgeRetrievalContext(False, "no_matches")

        context, refs = self._format_results(rows)
        if not context:
            return KnowledgeRetrievalContext(False, "no_usable_matches")
        return KnowledgeRetrievalContext(
            True,
            decision.reason,
            context=context,
            source_refs=refs,
        )

    def _format_results(
        self,
        rows: list[Any],
    ) -> tuple[str, tuple[str, ...]]:
        sections: list[str] = []
        refs: list[str] = []
        used_chars = 0

        for row in rows[: self.max_results]:
            if not isinstance(row, dict):
                continue
            ref = str(row.get("source_ref") or "").strip()
            content = str(row.get("content") or "").strip()
            if not ref or not content or ref in refs:
                continue

            content = content[: self.max_chunk_chars]
            data_lines = "\n".join(
                f"DATA | {line}" for line in content.splitlines()
            )
            section = f"[Source: {ref}]\n{data_lines}".strip()

            remaining = self.max_context_chars - used_chars
            if remaining <= 0:
                break
            if len(section) > remaining:
                section = section[:remaining].rstrip()
            if not section:
                break

            sections.append(section)
            refs.append(ref)
            used_chars += len(section) + 2

        return "\n\n".join(sections), tuple(refs)
