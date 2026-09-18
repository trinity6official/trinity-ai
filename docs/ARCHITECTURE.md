# Trinity AI Architecture

## Design principles

1. **Local runtime first.** The Mac is the authoritative runtime. Remote channels are adapters.
2. **Memory is independent from the model.** Changing models must not erase Trinity's identity/history.
3. **Models are replaceable.** Trinity talks to a provider-neutral local model router.
4. **Side effects are governed.** Tools, agents and computer actions pass through permission and audit layers.
5. **Raw sensory data is ephemeral by default.** Screenshots/audio should not become durable memory unless explicitly required.
6. **One Trinity runtime.** Voice, API, Presence and mobile all enter the same conversation/memory/tool pipeline.

## Core flow

```text
Input channel
    ↓
Message service / orchestrator
    ↓
Conversation service
    ├── Memory recall
    ├── Local model selection
    └── Tool/agent requests
            ↓
       Permission engine
            ↓
         Audit trail
            ↓
      Skill / Agent / Computer
            ↓
       Result + awareness events
            ↓
       Response processing
            ↓
Output channel + memory pipeline
```

## Local AI

`core/model_router.py` owns task routing and local failover. `core/models/` defines the provider-neutral interface; Ollama is the first implementation. `core/ai_service.py` loads defaults from `config/local_ai.yaml` and applies environment overrides.

Task routes are currently `fast`, `general`, `reasoning`, and `coding`. The configured model names remain provisional until measured on the actual M5 Pro 48 GB machine.

## Memory

Trinity separates four memory/state responsibilities:

- `MemoryService` + `MemoryStore`: the authoritative personal-memory boundary. SQLite owns structured profile/business state, searchable durable memory, and persistent conversation/session history.
- Markdown Memory Vault: human-readable high-value durable memory and daily history.
- Personal Knowledge: indexed approved files/documents, owned separately by the knowledge subsystem.
- `Consciousness`: runtime/experience state, working context, decisions and patterns under `memory/runtime/`; it is not a second personal-memory database.

Legacy JSON brain files are migration inputs only. Runtime skills receive the shared memory boundary instead of opening those files or constructing independent stores.

## Permission and audit

`core/permissions.py` classifies actions as safe, confirm, high-risk or forbidden. Unknown operations default to confirmation. `core/audit.py` records action lifecycle events while redacting sensitive values.

A generic pending-action queue allows an action that needs confirmation to pause and resume only after explicit approval.

## Agents and skills

`AgentRegistry` provides a single execution path for domain agents. Agents declare contracts such as allowed inputs, side effects, memory access and network access. Skills are dynamically discovered but execute through the same permission/audit controls.

## Awareness and proactive behavior

The event bus feeds `AwarenessEngine`, Presence and proactive services. Proactive behavior is allowed to reason and notify, but it does not bypass the permission engine or silently modify Trinity's own source code.

## Voice and vision

Voice uses local capture → local STT → Trinity → local TTS. The runtime supports wake-word/session handling and interruption; acoustic/model tuning must be completed on the actual Mac.

Vision uses local multimodal models. Screen awareness captures an image ephemerally, analyzes it locally, and avoids writing raw image bytes or vision descriptions into the action audit trail.

## Runtime and channels

`python -m core.run --mode daemon` starts the modern local runtime. `launchd` can keep it running after login/restart. Presence, API/mobile and local voice are interfaces owned by the same Trinity instance. User-facing output is routed through `core/output.py` rather than a transport-specific dependency.

GitHub Actions runs tests/build automation only. It does not run Trinity's consciousness and does not commit memory files.
