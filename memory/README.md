# `memory/` — Trinity Runtime Memory

Trinity's memory is local, model-independent, and separated by responsibility.

## Ownership after consolidation PR #4

- `trinity_memory.db` — authoritative SQLite store for:
  - structured personal/business state (`state_documents`),
  - searchable durable memory (`memories`), and
  - persistent conversation/session history (`conversation_turns`).
- `vault/` — human-readable Markdown mirror for high-value durable memories and daily activity.
- `runtime/` — runtime/experience state that is not personal-memory ownership; `consciousness.json` lives here.
- `knowledge_index.db` — personal document/knowledge indexing, owned by the knowledge subsystem rather than conversation memory.
- `trinity_brain.json` — optional **legacy migration source only**. It is not rewritten during normal operation.

`core.memory.MemoryService` is the runtime boundary that owns the shared `MemoryStore`. Skills and services receive that shared boundary/store instead of constructing competing memory stores.

The conversation-memory pipeline performs session persistence, extraction, importance/classification, deduplication, durable storage, and later recall. Changing the active local model must not erase or redefine Trinity's memory.

## Backup

Use:

```bash
python -m core.macos_deployment backup
```

The backup manager takes a transactionally consistent SQLite snapshot so committed WAL data is included safely. It also includes the Markdown vault and `memory/runtime/` state.

Restore requires explicit approval:

```bash
python -m core.macos_deployment restore /path/to/backup.tar.gz --approve
```

Do not commit legacy migration files, generated databases, Vault content, runtime state, backups, secrets, caches, or model weights to Git. CI enforces this boundary with `scripts/check_repository_hygiene.py`.
