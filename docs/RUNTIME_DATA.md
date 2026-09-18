# Runtime Data Boundary

Trinity's Git repository contains software, configuration templates, documentation, and tests. It must not contain the evolving state of a running Trinity instance.

## Repository vs runtime state

The following data is runtime state and remains local to the machine running Trinity:

- legacy brain JSON files used during the current memory migration period;
- SQLite memory databases and their WAL/SHM files;
- Markdown Memory Vault content;
- daily logs and action-audit logs;
- backups, PID files, caches, local model weights, and secrets.

These paths are ignored by Git. Fresh clones do not include personal memory or historical runtime state.

During the current consolidation phase, some runtime files are still created under the repository working tree (for example `memory/trinity_memory.db`, `memory/vault/`, `memory/runtime/`, and the legacy brain JSON paths). This PR establishes the **source-control boundary only**. Moving all runtime state to a dedicated Trinity home directory will be handled separately so memory migration and rollback can be designed safely.

## Legacy memory migration

`core.memory.TrinityMemory` and `core.consciousness.Consciousness` already tolerate missing legacy JSON files. If a local legacy brain file exists, Trinity can continue to read it during migration; the file is simply no longer version-controlled.

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
