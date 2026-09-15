from core.knowledge_index import KnowledgeIndex


class FakeEmbeddingProvider:
    key = "fake:test"

    def embed(self, texts):
        vectors = []
        for text in texts:
            value = text.lower()
            if "car" in value or "vehicle" in value or "automobile" in value:
                vectors.append([1.0, 0.0])
            elif "banana" in value or "fruit" in value:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([0.5, 0.5])
        return vectors


class BrokenEmbeddingProvider:
    key = "fake:broken"

    def embed(self, texts):
        raise RuntimeError("embedding service unavailable")


def test_hybrid_search_can_find_semantic_only_match(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    car = docs / "transport.md"
    car.write_text("The automobile maintenance schedule is documented here.", encoding="utf-8")
    fruit = docs / "food.md"
    fruit.write_text("Banana nutrition and fruit storage guidance.", encoding="utf-8")

    index = KnowledgeIndex(
        tmp_path / "knowledge.db",
        embedding_provider=FakeEmbeddingProvider(),
        auto_embedding_provider=False,
    )
    index.index_path(docs)

    assert index.search("vehicle", mode="lexical") == []
    semantic = index.search("vehicle", mode="semantic")
    hybrid = index.search("vehicle", mode="hybrid")

    assert semantic
    assert semantic[0].source_path == str(car.resolve())
    assert hybrid
    assert hybrid[0].source_path == str(car.resolve())
    assert index.status()["embedded_chunks"] == 2


def test_embedding_failure_falls_back_to_lexical(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("Phoenix local architecture", encoding="utf-8")
    index = KnowledgeIndex(
        tmp_path / "knowledge.db",
        embedding_provider=BrokenEmbeddingProvider(),
        auto_embedding_provider=False,
    )

    result = index.index_path(source)
    hits = index.search("Phoenix", mode="hybrid")

    assert result["indexed"] == 1
    assert hits
    assert hits[0].source_path == str(source.resolve())
    assert "unavailable" in (index.status()["embedding_error"] or "")
