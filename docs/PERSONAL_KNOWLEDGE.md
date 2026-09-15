# Trinity Personal Knowledge

Trinity's Personal Knowledge store is separate from conversation memory and web search. Only paths explicitly approved through `knowledge.index_knowledge_path` become readable knowledge roots.

## Supported documents

- Text, Markdown, source code, JSON/YAML/CSV and other existing text formats use line references such as `notes.md#L12-L20`.
- PDF files use page references such as `design.pdf#p4`.
- DOCX files use paragraph references such as `proposal.docx#P8-P12` because Word files do not expose stable rendered page numbers.

`pypdf` and `python-docx` are already part of the normal Trinity requirements.

## Search modes

`knowledge.search_knowledge` accepts `mode=lexical`, `semantic`, or `hybrid`. `hybrid` is the default. If no embedding provider is enabled or the provider is unavailable, hybrid search fails open to the lexical index.

### Mac-local embeddings

Install the optional Mac knowledge dependencies:

```bash
pip install -r requirements-knowledge-mac.txt
```

Then enable one local backend.

Sentence Transformers, fully in-process:

```bash
export TRINITY_KNOWLEDGE_EMBEDDINGS=sentence_transformers
export TRINITY_KNOWLEDGE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Ollama embeddings:

```bash
export TRINITY_KNOWLEDGE_EMBEDDINGS=ollama
export TRINITY_KNOWLEDGE_EMBEDDING_MODEL=nomic-embed-text
export TRINITY_KNOWLEDGE_EMBEDDING_URL=http://127.0.0.1:11434
```

An OpenAI-compatible **local** embedding endpoint is also supported with `TRINITY_KNOWLEDGE_EMBEDDINGS=openai_compatible`, `TRINITY_KNOWLEDGE_EMBEDDING_MODEL`, and `TRINITY_KNOWLEDGE_EMBEDDING_URL`.

No cloud embedding service is required.

## Automatic refresh

The always-on runtime refreshes already-approved roots incrementally. It does not discover or approve new roots on its own.

Defaults:

```bash
TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED=true
TRINITY_KNOWLEDGE_REFRESH_INTERVAL_SECONDS=900
```

Set `TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED=false` to disable background refresh.

## Security boundary

Indexed content is evidence, not executable instruction. Automatic retrieval only uses already-approved roots, respects the Trust/Permission engine, and injects retrieved text into the model as untrusted data with source references.
