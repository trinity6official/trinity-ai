"""Explicit execution contracts shared by Trinity task/capability boundaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ExecutionRequest:
    """One requested skill capability invocation.

    The request is immutable once it crosses the execution boundary so policy,
    audit, approval and the eventual capability invocation all refer to the same
    skill/tool/parameter tuple.
    """

    skill: str
    tool: str
    params: Mapping[str, Any] = field(default_factory=dict)
    approved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill", str(self.skill).strip().lower())
        object.__setattr__(self, "tool", str(self.tool).strip())
        object.__setattr__(self, "params", MappingProxyType(dict(self.params or {})))

    @property
    def action(self) -> str:
        return f"{self.skill}.{self.tool}"

    def approved_copy(self) -> "ExecutionRequest":
        return ExecutionRequest(
            skill=self.skill,
            tool=self.tool,
            params=self.params,
            approved=True,
        )

    def as_pending_action(self, approval_id: str, permission: str) -> dict[str, Any]:
        """Compatibility representation used by the existing approval UI/flow."""
        return {
            "id": approval_id,
            "skill": self.skill,
            "tool": self.tool,
            "params": dict(self.params),
            "permission": permission,
        }


@dataclass(frozen=True)
class AgentExecutionRequest:
    """One requested agent capability invocation.

    Agent execution uses the same immutable-request principle as skill execution:
    policy, audit and the handler all observe one stable objective/data tuple.
    """

    agent: str
    objective: str
    data: Mapping[str, Any] = field(default_factory=dict)
    approved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent", str(self.agent).strip().lower())
        object.__setattr__(self, "objective", str(self.objective))
        object.__setattr__(self, "data", MappingProxyType(dict(self.data or {})))

    def approved_copy(self) -> "AgentExecutionRequest":
        return AgentExecutionRequest(
            agent=self.agent,
            objective=self.objective,
            data=self.data,
            approved=True,
        )


@dataclass(frozen=True)
class TaskExecutionResult:
    """Normalized result of an LLM-requested task execution batch."""

    results: tuple[Any, ...]
    rendered_text: str

    @property
    def has_results(self) -> bool:
        return bool(self.results)

    @property
    def failed(self) -> bool:
        for result in self.results:
            if not isinstance(result, dict):
                continue
            if result.get("success") is False:
                return True
            if result.get("error") and "success" not in result:
                return True
        return False

    @property
    def unknown_tool(self) -> dict[str, Any] | None:
        for result in self.results:
            if not isinstance(result, dict):
                continue
            if result.get("unknown_tool") or "unknown tool:" in str(result.get("error", "")).lower():
                return result
        return None
