# Post-Consolidation Architecture Audit

Snapshot: 2026-09-19

This audit was performed after the seven-PR architecture consolidation. It checked the
tracked repository rather than relying only on the developer working tree, and reviewed
execution ownership, approvals, memory boundaries, capability discovery, CI behavior,
security-sensitive mutations, and local/remote interface assumptions.

## High-priority findings fixed in the audit-hardening pass

1. **CI could miss untracked internal modules during local development.** A local file
   could satisfy an import even when it was not staged, while a clean GitHub checkout
   failed. CI now validates internal imports against `git ls-files` and imports the
   production `core.trinity` composition root after dependencies are installed.
2. **Skill-evolution approval was not reviewable enough.** Generated Python was held in
   a private proposal while the user saw only a reason. Every proposal now exposes the
   exact unified diff on the active interface and through `/pending` before `YES` can
   apply the proposal.
3. **Execution-request immutability was shallow.** Nested dictionaries/lists could be
   mutated after the request crossed the permission/audit boundary. Skill and agent
   request payloads are now recursively snapshotted into immutable containers and
   explicitly thawed only at the execution boundary.
4. **`DebugSkill` missed its runtime dependency.** `SkillManager` now injects itself so
   `debug.test_skill_method` works in the real runtime, not only in isolated tests.
5. **Two read-only tools were incorrectly confirmation-gated.** Unit conversion and
   competitor research now have explicit safe policy classification.
6. **Capability availability could overstate readiness.** Model health exceptions/empty
   health maps now report unavailable, and voice readiness reflects actual local speech
   providers rather than merely the presence of a voice object.
7. **A stale `consciousness_skill.py` remained discoverable.** It did not implement the
   modern skill contract and duplicated the post-memory-consolidation responsibility
   boundary. It has been removed.
8. **CI full regression included real network tests.** The standard PR regression is now
   deterministic/offline (`-m "not network"`); explicitly marked network tests remain
   available for intentional manual runs.

## Boundaries confirmed healthy

- `MemoryService` / `MemoryStore` remains the single structured personal-memory owner.
- Legacy `trinity_brain.json` remains migration/backup input rather than active state.
- Telegram/transport-specific reasoning coupling remains removed.
- Skill execution still crosses `ExecutionRequest`; agent execution still crosses
  `AgentExecutionRequest` and the central permission/audit boundaries.
- Generated skill writes remain behind `SkillEvolutionService` and explicit approval.
- `CapabilityRegistry` remains a discovery/index layer and does not own execution.
- GitHub Actions remains CI/build automation only; it does not persist Trinity memory.

## Follow-up security work required before remote phone production use

These items are intentionally separated from this behavior-preserving audit-hardening
patch because they change the remote-access security contract:

1. **Remote API transport:** LAN examples and Android cleartext support currently permit
   HTTP. PIN/JWT credentials must not be considered transport protection. Production
   phone access should require an encrypted VPN path or HTTPS/TLS before remote binding
   is treated as commissioned.
2. **PIN storage:** the current SHA-256 PIN-hash comparison is not an appropriate
   password/PIN KDF for a low-entropy secret. Replace it with a salted, deliberately slow
   KDF and provide migration/commissioning guidance.
3. **Mobile policy:** align Android network-security configuration and setup docs with the
   final encrypted transport requirement.

## Lower-priority engineering debt

- Capability discovery currently loads skill implementations to obtain metadata; a later
  metadata-cache/static-manifest optimization can preserve lazy loading.
- Large legacy modules still exist (`SkillManager`, `Consciousness`, `KnowledgeIndex`,
  daemon code). Their ownership is now bounded, so further decomposition should be driven
  by measured maintenance/runtime need rather than another broad restructure.
- Dependencies are mostly unpinned; reproducible-lockfile work should follow hardware
  commissioning once the Mac dependency set is finalized.
- GitHub Actions currently emits an upstream Node runtime deprecation warning for older
  action majors; action upgrades should be verified separately rather than changed blindly.
- Proactive capability-gap notifications and user approval should eventually create the
  same concrete reviewable proposal used by interactive skill evolution.
