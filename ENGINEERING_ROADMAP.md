# Trinity AI Engineering Roadmap

## Consolidation PR sequence

- **PR #1 — Runtime Data Boundary:** complete.
- **PR #2 — Test Reliability Foundation:** complete.
- **PR #3 — Channel-Neutral Routing / Remote-Transport Removal:** complete.
- **PR #4 — Memory Ownership Consolidation:** complete in this change. `MemoryService` is the single personal-memory boundary; SQLite owns structured state, durable memory and session history; runtime consciousness state is separate.
- **PR #5 — Task/Execution Contracts + ConversationService Decomposition:** complete in this change. Skill execution now crosses an immutable `ExecutionRequest` boundary, and model-requested task handling is isolated in `ConversationTaskService` without changing the public `SkillManager.execute(...)` or conversation behavior.
- **PR #6 — Agent / Skill-Evolution Consolidation:** complete in this change. Agent execution now crosses an immutable request boundary, the legacy direct-writing `skill_builder` path is retired, and all generated skill changes flow through the governed `SkillEvolutionService` proposal/approval boundary.
- **PR #7 — Capability Registry:** complete in this change. Skill tools, agents and runtime features are indexed through one immutable normalized registry with explicit permission metadata and interface exposure; execution remains with the existing governed owners.

The seven-PR consolidation sequence is now complete. Further code changes should preserve these ownership boundaries rather than reopening parallel registries or execution paths.

## Post-consolidation audit hardening

The post-PR7 audit found several cross-environment and approval-boundary defects that are fixed in the audit-hardening pass: tracked-import CI verification, production composition-root import smoke testing, recursively immutable execution payloads, DebugSkill dependency injection, read-only permission corrections, truthful capability availability, removal of the stale consciousness skill, reviewable self-evolution diffs, and deterministic offline CI regression. See `docs/POST_CONSOLIDATION_AUDIT.md`.

Before production phone access is commissioned, complete a focused **API/mobile transport security hardening** pass covering encrypted remote transport and a slow salted PIN KDF.

## Completed in the local architecture upgrade

- Provider-neutral Local Model Router with Ollama adapter and local-only failover.
- YAML + environment model routing configuration.
- SQLite + Markdown Memory Vault and legacy migration.
- Conversation memory extraction/deduplication/recall.
- Consolidated memory ownership: one `MemoryService` / `MemoryStore` boundary for structured personal state, durable memory and session history; legacy JSON is migration-only and runtime consciousness state is isolated under `memory/runtime/`.
- Brain/orchestrator decomposition; `Trinity` is now primarily the composition root.
- Channel-neutral response routing and interface isolation.
- Central permission engine and shared action audit.
- Unified agent registry and agent capability contracts.
- Unified capability registry for skill/tool discovery, agent metadata, runtime availability and interface exposure.
- Event bus, awareness, proactive scheduling and duplicate suppression.
- Local voice abstraction, microphone runtime and wake-word/session controller.
- Local vision/screen-awareness framework with ephemeral image handling.
- Permission-gated computer control and generic resumable approval queue.
- Presence state engine and localhost visualizer.
- Secure local API/mobile bridge.
- macOS launchd/preflight/logging/backup/restore tooling.
- GitHub Actions repositioned to CI/build automation only.
- Architecture-contract regression tests.

## Hardware commissioning — requires the actual M5 Pro Mac

1. Benchmark installed local models and finalize fast/general/reasoning/coding routes.
2. Measure memory pressure/context behavior under realistic concurrent workloads.
3. Select and benchmark the local multimodal vision model.
4. Select/tune Whisper model and final TTS voice.
5. Tune wake-word sensitivity and acoustic barge-in in the real environment.
6. Validate macOS microphone, accessibility/automation and screen-recording permissions.
7. Validate phone API access over the intended LAN/VPN configuration.
8. Run restart, offline and model-failure recovery tests.
9. Run multi-hour and multi-day daemon soak tests and inspect memory growth/log rotation.
10. Finalize the measured model assignments in `config/local_ai.yaml`.

## Post-commissioning enhancements

- Add MLX and/or llama.cpp adapters if benchmarking shows a material benefit.
- Improve the Presence visual design after runtime state behavior is proven.
- Add additional permission-reviewed external connectors only as actual workflows require them.
- Continue agent specialization using explicit contracts rather than adding autonomous privileges globally.
