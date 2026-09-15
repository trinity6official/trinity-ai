"""Local-only model routing and failover for Trinity AI."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, Iterable, Optional, Sequence

from core.models import (
    ChatMessage,
    LocalModelError,
    LocalModelProvider,
    LocalModelUnavailableError,
    OllamaProvider,
)


@dataclass(frozen=True)
class ModelRoute:
    task: str
    model: str
    provider: str


class LocalChatModel:
    """LangChain-compatible facade while legacy orchestration is migrated."""

    def __init__(self, router, task):
        self.router, self.task = router, task

    def invoke(self, messages):
        converted = []
        for msg in messages:
            explicit_role = getattr(msg, "role", None)
            if explicit_role in {"system", "user", "assistant"}:
                role = explicit_role
            else:
                name = type(msg).__name__.lower()
                role = "system" if "system" in name else "assistant" if "ai" in name else "user"
            converted.append(ChatMessage(role, str(getattr(msg, "content", msg))))
        return SimpleNamespace(content=self.router.chat(converted, task=self.task))


class LocalModelRouter:
    """Route by task and fail over only across local providers/models."""

    TASK_ALIASES = {
        "chat": "general",
        "fast": "fast",
        "general": "general",
        "reasoning": "reasoning",
        "coding": "coding",
    }

    DEFAULT_MODELS = {
        "fast": "qwen3:8b",
        "general": "qwen3:14b",
        "reasoning": "qwen3:30b",
        "coding": "qwen3:14b",
    }

    def __init__(
        self,
        providers: Optional[Sequence[LocalModelProvider]] = None,
        models: Optional[Dict[str, str | Sequence[str]]] = None,
    ):
        self.providers = list(providers or [OllamaProvider()])
        configured = models or self.DEFAULT_MODELS
        self.models = {
            task: self._normalize_candidates(value)
            for task, value in configured.items()
        }

    @staticmethod
    def _normalize_candidates(value: str | Sequence[str]) -> tuple[str, ...]:
        if isinstance(value, str):
            candidates = [item.strip() for item in value.split(",") if item.strip()]
        else:
            candidates = [str(item).strip() for item in value if str(item).strip()]
        if not candidates:
            raise ValueError("At least one local model candidate is required")
        return tuple(dict.fromkeys(candidates))

    def _task(self, task: str) -> str:
        normalized = self.TASK_ALIASES.get(task.lower(), task.lower())
        if normalized not in self.models:
            raise ValueError(f"No local model configured for task '{normalized}'")
        return normalized

    def resolve_model(self, task="general") -> ModelRoute:
        """Return the preferred configured route without making a network call."""
        normalized = self._task(task)
        return ModelRoute(normalized, self.models[normalized][0], self.providers[0].name)

    def configured_models(self, task: str = "general") -> tuple[str, ...]:
        return self.models[self._task(task)]

    def _attempts(self, task: str, explicit_model: str | None = None) -> Iterable[ModelRoute]:
        normalized = self._task(task)
        candidates = (explicit_model,) if explicit_model else self.models[normalized]
        for model in candidates:
            for provider in self.providers:
                yield ModelRoute(normalized, model, provider.name)

    def _provider(self, name):
        provider = next((p for p in self.providers if p.name == name), None)
        if provider is None:
            raise ValueError(f"Unknown provider: {name}")
        return provider

    def chat(self, messages, task="general", model=None, **kwargs):
        errors: list[str] = []
        for route in self._attempts(task, model):
            provider = self._provider(route.provider)
            try:
                if not provider.health():
                    errors.append(f"{route.provider}: unavailable")
                    continue
                return provider.chat(messages, route.model, **kwargs)
            except LocalModelError as exc:
                errors.append(f"{route.provider}/{route.model}: {exc}")
        detail = "; ".join(errors) or "no local routes configured"
        raise LocalModelUnavailableError(f"All local model routes failed: {detail}")

    def stream_chat(self, messages, task="general", model=None, **kwargs):
        errors: list[str] = []
        for route in self._attempts(task, model):
            provider = self._provider(route.provider)
            try:
                if not provider.health():
                    errors.append(f"{route.provider}: unavailable")
                    continue
                produced = False
                for chunk in provider.stream_chat(messages, route.model, **kwargs):
                    produced = True
                    yield chunk
                return
            except LocalModelError as exc:
                errors.append(f"{route.provider}/{route.model}: {exc}")
                if produced:
                    # Never splice a second model into a partially streamed answer.
                    raise
        detail = "; ".join(errors) or "no local routes configured"
        raise LocalModelUnavailableError(f"All local model routes failed: {detail}")

    def health(self):
        return {provider.name: provider.health() for provider in self.providers}

    def available_models(self):
        models = []
        for provider in self.providers:
            try:
                models.extend(provider.available_models())
            except LocalModelError:
                continue
        return models

    def model(self, task="general"):
        return LocalChatModel(self, task)
