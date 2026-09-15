"""Optional local embedding backends for Trinity knowledge search."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol, Sequence
from urllib.parse import urlparse


class EmbeddingProvider(Protocol):
    @property
    def key(self) -> str: ...
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _validate_local_endpoint(url: str) -> str:
    allow_remote = os.environ.get(
        "TRINITY_KNOWLEDGE_ALLOW_REMOTE_EMBEDDINGS", "false"
    ).strip().lower() in {"1", "true", "yes"}
    host = (urlparse(url).hostname or "").lower()
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if not allow_remote and host not in local_hosts:
        raise RuntimeError(
            "Knowledge embedding endpoint must be loopback-local unless "
            "TRINITY_KNOWLEDGE_ALLOW_REMOTE_EMBEDDINGS=true is explicitly set"
        )
    return url


@dataclass
class SentenceTransformerEmbeddingProvider:
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str | None = None

    def __post_init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "sentence-transformers is not installed; use requirements-knowledge-mac.txt"
            ) from exc
        kwargs = {}
        if self.device:
            kwargs["device"] = self.device
        self._model = SentenceTransformer(self.model_name, **kwargs)

    @property
    def key(self) -> str:
        return f"sentence_transformers:{self.model_name}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in row] for row in vectors]


@dataclass
class OllamaEmbeddingProvider:
    model_name: str = "nomic-embed-text"
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 30.0

    @property
    def key(self) -> str:
        return f"ollama:{self.model_name}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        import requests

        response = requests.post(
            f"{self.base_url.rstrip('/')}/api/embed",
            json={"model": self.model_name, "input": list(texts)},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise RuntimeError("Ollama embedding response did not contain expected embeddings")
        return [[float(value) for value in row] for row in vectors]


@dataclass
class OpenAICompatibleEmbeddingProvider:
    model_name: str
    base_url: str = "http://127.0.0.1:8081/v1"
    api_key: str | None = None
    timeout_seconds: float = 30.0

    @property
    def key(self) -> str:
        return f"openai_compatible:{self.model_name}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        import requests

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            f"{self.base_url.rstrip('/')}/embeddings",
            headers=headers,
            json={"model": self.model_name, "input": list(texts)},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("Embedding response did not contain data")
        rows = sorted(rows, key=lambda item: int(item.get("index", 0)))
        vectors = [item.get("embedding") for item in rows]
        if len(vectors) != len(texts) or any(not isinstance(row, list) for row in vectors):
            raise RuntimeError("Embedding response did not contain expected vectors")
        return [[float(value) for value in row] for row in vectors]


def build_embedding_provider_from_env() -> EmbeddingProvider | None:
    mode = os.environ.get("TRINITY_KNOWLEDGE_EMBEDDINGS", "off").strip().lower()
    if mode in {"", "0", "false", "no", "off", "disabled"}:
        return None

    model = os.environ.get("TRINITY_KNOWLEDGE_EMBEDDING_MODEL", "").strip()
    if mode in {"sentence_transformers", "sentence-transformers", "st"}:
        return SentenceTransformerEmbeddingProvider(
            model_name=model or "sentence-transformers/all-MiniLM-L6-v2",
            device=os.environ.get("TRINITY_KNOWLEDGE_EMBEDDING_DEVICE") or None,
        )
    if mode == "ollama":
        return OllamaEmbeddingProvider(
            model_name=model or "nomic-embed-text",
            base_url=_validate_local_endpoint(os.environ.get(
                "TRINITY_KNOWLEDGE_EMBEDDING_URL", "http://127.0.0.1:11434"
            )),
            timeout_seconds=float(os.environ.get("TRINITY_KNOWLEDGE_EMBEDDING_TIMEOUT", "30")),
        )
    if mode in {"openai_compatible", "openai-compatible", "local_http"}:
        if not model:
            raise RuntimeError(
                "TRINITY_KNOWLEDGE_EMBEDDING_MODEL is required for openai_compatible mode"
            )
        return OpenAICompatibleEmbeddingProvider(
            model_name=model,
            base_url=_validate_local_endpoint(os.environ.get(
                "TRINITY_KNOWLEDGE_EMBEDDING_URL", "http://127.0.0.1:8081/v1"
            )),
            api_key=os.environ.get("TRINITY_KNOWLEDGE_EMBEDDING_API_KEY") or None,
            timeout_seconds=float(os.environ.get("TRINITY_KNOWLEDGE_EMBEDDING_TIMEOUT", "30")),
        )
    raise RuntimeError(f"Unknown TRINITY_KNOWLEDGE_EMBEDDINGS mode: {mode}")
