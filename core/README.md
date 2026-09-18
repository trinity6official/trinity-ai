# `core/` — Trinity Runtime

`core/` contains Trinity's primary application/runtime logic. `core/trinity.py` is now a composition root and compatibility surface; most behavior is separated into focused services rather than implemented in one monolithic class.

## High-level flow

```text
Input/channel
   ↓
MessageService / Orchestrator
   ↓
ConversationService
   ├── Memory recall
   ├── Local AI routing
   └── Tool/agent requests
           ↓
      PermissionEngine
           ↓
        ActionAudit
           ↓
 Skill / Agent / Computer
           ↓
Events → Awareness → Presence / Proactive behavior
```

## Important modules

- `trinity.py` — composition root; wires the major services together.
- `run.py` — canonical runtime entrypoint (`daemon`, `oneshot`, `ci`).
- `runtime.py` / `lifecycle.py` — runtime-mode and lifecycle control.
- `conversation.py` — prompt/context assembly and local-model conversation reasoning.
- `conversation_tasks.py` — model-requested task execution, status output, missing-capability proposals, and one-shot tool-result follow-up.
- `execution.py` — immutable execution request/result contracts shared by task/capability boundaries.
- `message_service.py` / `orchestrator.py` / `commands.py` — message/command routing and approval handling.
- `ai_service.py` / `model_router.py` — local AI stack construction and task routing.
- `models/` — provider-neutral model interfaces and Ollama adapter.
- `memory.py` / `memory_store.py` / `memory_pipeline.py` — single personal-memory boundary, authoritative SQLite structured state, durable recall, and persistent sessions.
- `consciousness.py` — runtime/experience state, working memory, decisions and patterns stored separately under `memory/runtime/`.
- `permissions.py` — safe/confirm/high-risk/forbidden policy.
- `audit.py` — redacted action lifecycle audit.
- `agent_runtime.py` / `agent_bootstrap.py` — unified agent registry, immutable agent execution requests, and capability contracts.
- `capabilities.py` — normalized capability index for skills/tools, agents, runtime availability, permissions, and per-interface exposure.
- `skill_manager.py` — skill discovery plus the governed `ExecutionRequest` permission/audit execution boundary.
- `events.py` / `awareness.py` — event bus and live context.
- `proactive.py` / `proactive_service.py` / `scheduler.py` — proactive reasoning and scheduled work.
- `presence.py` / `presence_web.py` — local state model and visualizer.
- `computer.py` — permission-gated macOS computer operations.
- `vision.py` / `perception.py` — local multimodal vision and screen awareness.
- `api.py` / `api_runtime.py` / `api_bridge.py` / `api_security.py` — authenticated API bound to the full Trinity runtime.
- `output.py` — channel-neutral response routing for API, mobile, voice, CLI, and future interfaces.
- `attachments.py` — channel-neutral document/photo analysis.
- `notifications.py` — delivery abstraction used by compatibility/proactive flows.
- `macos_deployment.py` / `doctor.py` — Mac preflight, LaunchAgent preparation, diagnostics, and memory backup/restore.
- `model_benchmark.py` — local-model performance measurement.
- `change_requests.py` / `skill_evolution.py` — approval-gated code change/self-improvement workflow; generated skill changes have no direct-write bypass.

## Rules for new core features

1. Do not add cloud LLM routing to the core runtime.
2. Do not persist Trinity memory to Git.
3. Do not bypass `PermissionEngine` for side effects.
4. Emit audit events for meaningful actions and redact secrets.
5. Publish runtime state through the event bus rather than tightly coupling observers.
6. Keep raw audio/screenshots ephemeral unless persistence is explicitly required.
7. Keep interface-specific transport logic outside reasoning/services and route responses through `output.py`.
8. Prefer adding a focused service over growing `trinity.py` again.

Run `python -m pytest -q` after changes and keep `tests/test_architecture_contract.py` green.
