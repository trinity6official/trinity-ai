# `memory/` — Trinity Memory

Trinity's memory is local and independent from any language model.

## Layers

- `trinity_brain.json` — preserved legacy brain/migration source.
- `trinity_memory.db` — runtime-created SQLite operational memory (ignored by Git).
- `vault/` — runtime-created human-readable Markdown Memory Vault (ignored by Git).
- `runtime/` — ephemeral/runtime metadata created locally.
- `daily_logs/` — runtime-generated logs created locally.

The Memory Vault pipeline performs extraction, importance/classification, deduplication, storage, and later recall. Changing the active local model should not erase or redefine Trinity's memory.

## Backup

Use:

```bash
python -m core.macos_deployment backup
```

The backup manager takes a transactionally consistent SQLite snapshot so committed WAL data is included safely.

Restore requires explicit approval:

```bash
python -m core.macos_deployment restore /path/to/backup.tar.gz --approve
```

Do not commit generated databases, Vault content, secrets, caches, or model weights to Git.
