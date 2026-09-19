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

**PR #11 — API / Mobile Security Hardening:** complete in this change. Remote binding now requires a salted PBKDF2 PIN verifier, strong JWT secret, explicit HTTPS/TLS or specifically bound encrypted-VPN transport, non-wildcard remote CORS, bounded JWT sessions, and failed-login lockout.

Repository simplification is now complete in two passes. PR #9 retired proven-dead compatibility runtimes, duplicate modules and the second hard-coded skill capability catalog. PR #10 removes the remaining `Trinity` forwarding facade, moves briefing/status aggregation out of `SkillManager`, and retires the obsolete block-style skill-call protocol so only the documented inline contract remains.

## Next engineering sequence

The consolidation sequence is complete, but the Trinity product roadmap is not. Continue in this order while preserving the ownership boundaries above:

1. **PR #12 — Process Manager:** complete in this change. SQLite-backed process lifecycle state now covers progress, cancellation, cooperative timeouts, bounded retries and restart recovery; handlers delegate actual work to existing governed execution owners.
2. **PR #13 — Persistent Scheduler:** complete in this change. Recurring and one-shot schedules persist in SQLite, submit crash-idempotent occurrences into Process Manager, survive restarts, skip interval backlog bursts, and retain the existing scheduler lifecycle events.
3. **PR #14 — MCP Foundation:** complete. Dependency-light stdio JSON-RPC transport, configured server lifecycle, paginated tool discovery, health, explicit environment allowlisting, bounded request timeouts and restart handling.
4. **PR #15 — MCP → Capability Registry:** complete. Cached MCP discoveries are normalized into stable runtime-only `CapabilityDescriptor` entries; registry reads remain side-effect-free and execution stays disabled pending governance.
5. **PR #16 — MCP Governance:** complete. MCP execution is isolated behind `MCPExecutionService` with exact tool allowlists, server trust policy, Trinity permissions, explicit approvals, bounded results, and shared action audit integration.
6. **PR #17 — Objective / Focus Foundation:** complete in this change. Explicit user objectives and current focus persist inside the existing MemoryService ownership boundary, retain lifecycle/history when priorities change, and expose only bounded non-terminal context to reasoning. This layer stores intent only; it does not schedule or execute work.
7. **PR #18 — Event-driven Cognitive Coordinator:** complete in this change. Only explicitly objective-linked terminal process events are evaluated. Cheap deterministic progress/blocking updates use explicit process metadata; events needing judgment enqueue an `objective.review` process so the synchronous EventBus never performs model inference. The existing ProactiveService owns reasoning, and the coordinator owns no skill/MCP/agent execution.
8. **PR #19 — Explicit Objective Controls:** complete in this change. Slash commands now let David create, list, focus, pause, resume, update progress, complete, abandon and clear focus without relying on model inference. Command arguments remain intact through MessageService, transient runtime focus is displayed separately from durable objective focus, and the primary conversation prompt is domain-neutral.
9. **Behavior validation before further autonomy:** exercise real objective-linked workflows and observe whether Trinity chooses useful moments to reason. The next implementation change must be justified by a concrete workflow gap; do not add a generic autonomous action planner by default.
10. **Optional Trinity MCP Server:** deferred until an actual external local MCP-client use case requires Trinity to expose capabilities outward.
11. **Post-autonomy / hardware:** validate real workflows first, then finalize model routing/residency from measured Mac hardware behavior; continue workflow learning, progressive/lazy capability loading, browser/macOS automation expansion, test-performance cleanup, and long-duration evaluation.

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

## Hardware commissioning — requires the actual M6 Mac mini 32 GB

1. Benchmark installed local models and finalize fast/general/reasoning/coding routes.
2. Measure memory pressure/context behavior under realistic concurrent workloads.
3. Select and benchmark the local multimodal vision model.
4. Select/tune Whisper model and final TTS voice.
5. Tune wake-word sensitivity and acoustic barge-in in the real environment.
6. Validate macOS microphone, accessibility/automation and screen-recording permissions.
7. Validate phone API access over the intended HTTPS or encrypted-VPN configuration.
8. Run restart, offline and model-failure recovery tests.
9. Run multi-hour and multi-day daemon soak tests and inspect memory growth/log rotation.
10. Finalize the measured model assignments in `config/local_ai.yaml`.

## Post-commissioning enhancements

- Add MLX and/or llama.cpp adapters if benchmarking shows a material benefit.
- Improve the Presence visual design after runtime state behavior is proven.
- Add additional permission-reviewed external connectors only as actual workflows require them.
- Continue agent specialization using explicit contracts rather than adding autonomous privileges globally.
