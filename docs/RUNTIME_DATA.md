# Runtime Data Boundary

Trinity's Git repository contains software, configuration templates, documentation, and tests. It must not contain the evolving state of a running Trinity instance.

## Repository vs runtime state

The following data is runtime state and remains local to the machine running Trinity:

- legacy brain JSON files retained only as migration/recovery inputs;
- SQLite memory databases and their WAL/SHM files;
- Markdown Memory Vault content;
- `memory/runtime/` consciousness/runtime state, daily history and action-audit logs;
- backups, PID files, caches, local model weights, and secrets.

These paths are ignored by Git. Fresh clones do not include personal memory or historical runtime state.

During the current consolidation phase, runtime files are still created under the repository working tree (for example `memory/trinity_memory.db`, `memory/vault/`, `memory/runtime/`, and the personal-knowledge index). Moving all runtime state to a dedicated Trinity home directory will be handled separately so migration and rollback can be designed safely.

## Legacy memory migration

`core.memory.MemoryService` imports `memory/trinity_brain.json` only when authoritative structured state has not yet been created in SQLite. After that first migration, later edits to the legacy JSON cannot overwrite SQLite state. `core.consciousness.Consciousness` similarly accepts the historical root brain file only when the new `memory/runtime/consciousness.json` snapshot does not yet exist.

Before a memory-architecture migration or major refactor, create and verify a local backup. On supported installs:

```bash
python -m core.macos_deployment backup
```

Do not add the resulting backup archive to Git.

## Repository guardrail

CI runs:

```bash
python scripts/check_repository_hygiene.py --git-index
```

The check fails if Git tracks known runtime, cache, secret, database, backup, or local-model paths. This prevents ignored files from being accidentally reintroduced with `git add -f` or from remaining tracked after ignore rules change.
