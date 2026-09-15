import pytest

from core.knowledge_embeddings import build_embedding_provider_from_env


def test_embedding_endpoint_defaults_to_local_only(monkeypatch):
    monkeypatch.setenv("TRINITY_KNOWLEDGE_EMBEDDINGS", "ollama")
    monkeypatch.setenv("TRINITY_KNOWLEDGE_EMBEDDING_URL", "https://example.com")
    monkeypatch.delenv("TRINITY_KNOWLEDGE_ALLOW_REMOTE_EMBEDDINGS", raising=False)

    with pytest.raises(RuntimeError, match="loopback-local"):
        build_embedding_provider_from_env()


def test_remote_embedding_endpoint_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("TRINITY_KNOWLEDGE_EMBEDDINGS", "ollama")
    monkeypatch.setenv("TRINITY_KNOWLEDGE_EMBEDDING_URL", "https://example.com")
    monkeypatch.setenv("TRINITY_KNOWLEDGE_ALLOW_REMOTE_EMBEDDINGS", "true")

    provider = build_embedding_provider_from_env()
    assert provider.base_url == "https://example.com"
