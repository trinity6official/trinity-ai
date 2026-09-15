"""Local AI task selection and invocation for Trinity."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.model_router import LocalModelRouter
from core.models import LlamaCppProvider, OllamaProvider


@dataclass(frozen=True)
class LocalAIStack:
    """Configured local-AI components used by the Trinity composition root."""

    router: LocalModelRouter
    service: "LocalAIService"
    default_model: Any
    general_model_name: str
    ollama_available: bool
    base_url: str
    provider_name: str = "ollama"
    provider_available: bool = False


DEFAULT_LOCAL_AI_CONFIG = Path(__file__).resolve().parent.parent / "config" / "local_ai.yaml"


def _load_local_ai_config(env: Mapping[str, str]) -> dict[str, Any]:
    """Load local-AI defaults from YAML without making configuration mandatory."""
    path = Path(env.get("TRINITY_LOCAL_AI_CONFIG", str(DEFAULT_LOCAL_AI_CONFIG))).expanduser()
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Unable to read local AI config {path}: {exc}") from exc
    section = payload.get("local_ai", {})
    if not isinstance(section, dict):
        raise RuntimeError(f"Invalid local_ai section in {path}")
    return section


def _preferred_model(value: str | list[str] | tuple[str, ...]) -> str:
    if isinstance(value, str):
        return value.split(",", 1)[0].strip()
    return str(value[0]).strip()


def build_local_ai_from_environment(environ: Mapping[str, str] | None = None) -> LocalAIStack:
    """Build Trinity's local-only model stack from YAML defaults + env overrides."""
    env = environ if environ is not None else os.environ
    config = _load_local_ai_config(env)
    provider_name = str(config.get("provider", "ollama")).strip().lower()
    default_base_url = (
        "http://127.0.0.1:8080" if provider_name in {"llama_cpp", "llama.cpp"}
        else "http://127.0.0.1:11434"
    )
    base_url = env.get(
        "LOCAL_LLM_URL",
        str(config.get("base_url", default_base_url)),
    )
    if provider_name == "ollama":
        provider = OllamaProvider(base_url=base_url)
        normalized_provider_name = "ollama"
    elif provider_name in {"llama_cpp", "llama.cpp"}:
        provider = LlamaCppProvider(base_url=base_url)
        normalized_provider_name = "llama_cpp"
    else:
        raise RuntimeError(
            f"Unsupported local AI provider '{provider_name}'. "
            "Supported local providers: ollama, llama_cpp."
        )
    configured_tasks = config.get("tasks") or config.get("models") or {}
    if not isinstance(configured_tasks, dict):
        raise RuntimeError("local_ai.tasks must be a mapping")

    defaults = LocalModelRouter.DEFAULT_MODELS
    models = {
        "fast": env.get("TRINITY_FAST_MODEL") or configured_tasks.get("fast") or defaults["fast"],
        "general": env.get("TRINITY_GENERAL_MODEL") or configured_tasks.get("general") or defaults["general"],
        "reasoning": env.get("TRINITY_REASONING_MODEL") or configured_tasks.get("reasoning") or defaults["reasoning"],
        "coding": env.get("TRINITY_CODING_MODEL") or configured_tasks.get("coding") or defaults["coding"],
    }
    router = LocalModelRouter(
        providers=[provider],
        models=models,
    )
    service = LocalAIService(router)
    available = bool(router.health().get(normalized_provider_name))
    return LocalAIStack(
        router=router,
        service=service,
        default_model=router.model("general"),
        general_model_name=_preferred_model(models["general"]),
        ollama_available=(available if normalized_provider_name == "ollama" else False),
        base_url=base_url,
        provider_name=normalized_provider_name,
        provider_available=available,
    )


class LocalAIService:
    """Owns task classification and access to the local model router."""

    CODING_KEYWORDS = (
        "code", "debug", "refactor", "implement", "function", "python", "ruby", "golang"
    )
    REASONING_KEYWORDS = (
        "analyze", "architecture", "design", "compare", "step by step", "comprehensive", "reason"
    )

    def __init__(self, router: LocalModelRouter) -> None:
        self.router = router

    def classify_task(self, question: str) -> str:
        q = (question or "").lower()
        if "```" in question or any(keyword in q for keyword in self.CODING_KEYWORDS):
            return "coding"
        if len(question) > 200 or any(keyword in q for keyword in self.REASONING_KEYWORDS):
            return "reasoning"
        return "general"

    def model_for(self, question: str):
        return self.router.model(self.classify_task(question))

    @staticmethod
    def label(model: Any) -> str:
        task = getattr(model, "task", "general")
        return f"Local AI ({task})"

    def invoke(self, messages, *, model=None):
        selected = model or self.router.model("general")
        try:
            return selected.invoke(messages)
        except Exception as exc:
            raise RuntimeError(f"Local AI invocation failed: {exc}") from exc
