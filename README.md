# Trinity AI

Trinity AI is a **local-first personal AI runtime** designed to run continuously on an Apple Silicon Mac while keeping its identity, memory, permissions, tools, agents, voice, vision, and computer interaction independent from any single language model.

The target production host is a **Mac mini with Apple M5 Pro and 48 GB unified memory**. The Mac is the authoritative Trinity runtime. Local voice, the mobile app, the HTTP API, and the Presence UI are interfaces into that same runtime; they do not host a second brain.

## What Trinity is

Trinity is not just a chat wrapper around a model. Its runtime separates reasoning from long-lived state and side effects:

```text
                           Trinity AI
                               │
                      Message / Orchestrator
                               │
                   Conversation + Context Layer
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
     Memory                 Awareness               Agents
 SQLite + Vault          Events + Presence      Registry + Skills
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
                    Permission + Action Audit
                               │
                       Local Model Router
                               │
                  Ollama / future local runtimes
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
     Voice                   Vision                 Computer
 Local STT/TTS         Local multimodal       macOS automation
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
           Local UI / API / Mobile / Voice / Presence
```

## Core design principles

1. **Local runtime first** — Trinity's brain runs on the Mac, not GitHub Actions or a cloud LLM service.
2. **Memory belongs to Trinity, not the model** — models can be swapped without losing identity or history.
3. **Models are replaceable** — task routing uses a provider-neutral local model interface.
4. **Side effects require policy** — skills, agents, computer actions, and restores pass through permission rules.
5. **Actions are auditable** — meaningful operations emit requested/approved/started/completed/failed audit events.
6. **Raw sensory data is ephemeral by default** — audio and screenshots are processed locally and are not automatically written into durable memory.
7. **One Trinity runtime** — voice, API, Presence, and mobile all enter the same conversation/memory/tool pipeline.
8. **Channel-neutral output** — core reasoning emits through a response router instead of depending on a specific transport.

## Current capabilities

- Provider-neutral local model routing with Ollama as the first runtime.
- Task routes for `fast`, `general`, `reasoning`, and `coding` with local failover.
- Runtime model configuration from `config/local_ai.yaml` plus environment overrides.
- Model benchmark tooling for time-to-first-token, latency, and approximate throughput.
- SQLite operational memory plus a human-readable Markdown Memory Vault.
- Legacy JSON brain migration while preserving original source data.
- Conversation-memory extraction, classification, deduplication, and recall.
- Central safe / confirm / high-risk / forbidden permission policy.
- Append-only action audit for tools, agents, computer actions, and protected operations.
- Generic pending-action queue so confirmation-gated actions can resume after explicit approval.
- Unified `AgentRegistry` with immutable execution requests and explicit capability contracts.
- Dynamic skills routed through the same permission and audit controls, with generated skill changes isolated behind one approval-gated evolution service.
- Event bus, awareness engine, proactive scheduling, duplicate suppression, and failure isolation.
- Local voice abstraction, wake-word/session handling, continuous microphone runtime, and interruption handling.
- Local multimodal vision plus privacy-aware screen awareness.
- Permission-gated macOS computer control.
- Local Presence state engine and localhost visualizer.
- Authenticated API/mobile bridge bound to the same Trinity runtime.
- Channel-neutral response routing for API, mobile, local voice, CLI, and future interfaces.
- macOS `launchd` deployment support, local logs, preflight checks, Doctor diagnostics, and safe Memory Vault backup/restore.
- GitHub Actions for CI/build automation only — never for Trinity memory persistence or consciousness runtime.

## Repository layout

| Folder | Purpose |
|---|---|
| `core/` | Trinity composition root, orchestration, memory services, permissions, agents, runtime, API, Presence, vision, deployment helpers |
| `core/models/` | Provider-neutral local-model types and adapters |
| `core/output.py` | Channel-neutral response routing for API, mobile, voice, CLI, and future interfaces |
| `memory/` | Legacy migration data plus runtime-created SQLite/Vault state |
| `agents/` | Domain-specific agents registered through the central agent runtime |
| `skills/` | Dynamically discoverable Trinity tools |
| `voice/` | Local capture, STT/TTS, wake-word/session, and voice runtime components |
| `config/` | Local AI and Trinity runtime configuration |
| `deployment/` | Platform deployment helpers; macOS is the primary deployment target |
| `scripts/` | Operator/install helper scripts |
| `mobile/` | Thin authenticated client for the Mac-hosted Trinity API |
| `tests/` | Regression, resilience, security, and architecture-contract tests |
| `docs/` | Architecture, security, Mac setup, and supporting documentation |
| `.github/` | CI and mobile build automation only |
| `raspberry_pi/` | Legacy/optional lightweight compatibility path, not the primary Trinity runtime |

Every major folder contains its own README explaining its responsibilities and boundaries.

## macOS quick start

Detailed instructions are in [`deployment/macos/README.md`](deployment/macos/README.md).

### 1. Create a Python environment

```bash
cd /path/to/trinity-ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
```

### 2. Install and start Ollama

Install Ollama for macOS, start it, and install the local models you want Trinity to benchmark/use. Model names in `config/local_ai.yaml` are provisional until measured on the actual M5 Pro.

### 3. Run preflight and Trinity Doctor

```bash
python -m core.macos_deployment preflight
python -m core.doctor
```

Doctor verifies the local runtime prerequisites, Ollama/model availability, Memory Vault writability, API security posture, and optional voice/vision readiness.

### 4. Benchmark local models

```bash
python -m core.model_benchmark --task fast --runs 3
python -m core.model_benchmark --task general --runs 3
python -m core.model_benchmark --task reasoning --runs 3
python -m core.model_benchmark --task coding --runs 3
```

Use the results to update `config/local_ai.yaml` or override routes with environment variables.

### 5. Run Trinity interactively/locally

```bash
python -m core.run --mode daemon
```

### 6. Prepare the LaunchAgent

```bash
./scripts/install_macos.sh
```

or:

```bash
python -m core.macos_deployment install
```

The Python deployment helper prepares the LaunchAgent but intentionally does not load it automatically. Review the generated plist first. The deployment README includes the `launchctl` enable/disable commands.

## Local AI configuration

Default routes live in `config/local_ai.yaml`:

```yaml
local_ai:
  provider: ollama
  base_url: http://127.0.0.1:11434
  tasks:
    fast: [qwen3:8b, qwen3:14b]
    general: [qwen3:14b, qwen3:8b]
    reasoning: [qwen3:30b, qwen3:14b, qwen3:8b]
    coding: [qwen3:14b, qwen3:30b, qwen3:8b]
```

Environment variables take priority when present:

```bash
export LOCAL_LLM_URL=http://127.0.0.1:11434
export TRINITY_FAST_MODEL=<installed-model>
export TRINITY_GENERAL_MODEL=<installed-model>
export TRINITY_REASONING_MODEL=<installed-model>
export TRINITY_CODING_MODEL=<installed-model>
export TRINITY_VISION_MODEL=<optional-installed-vision-model>
```

Do not treat the example model names as final M5 Pro choices until the benchmark harness has been run on the production Mac.

## Pre-M5 Samsung test mode

Before the M5 arrives, Trinity can run a reduced local acceptance harness on a Samsung/Android phone using Termux + `llama.cpp`. This is intentionally separate from the production macOS runtime.

See [`docs/ANDROID_PRE_HARDWARE_TEST.md`](docs/ANDROID_PRE_HARDWARE_TEST.md).

```bash
./scripts/install_android_test.sh
./scripts/start_android_model.sh ~/YOUR_MODEL.gguf
# in a second Termux session
./scripts/android_doctor.sh
./scripts/run_android_test.sh
```

This mode is for testing conversation, durable memory, and Android voice plumbing. Final model quality, vision/screen awareness, macOS permissions, and always-on deployment are still certified on the M5.

## Memory architecture

Trinity separates personal/session memory, document knowledge, and runtime state:

```text
Conversation
    ↓
Memory extraction
    ↓
Importance / classification / deduplication
    ↓
MemoryService (single owner)
    ↓
┌──────────────────────────────┬─────────────────────────┐
│ SQLite MemoryStore           │ Markdown Memory Vault   │
│ structured profile state     │ human-readable durable  │
│ durable searchable memories  │ memory + daily history  │
│ persistent session history   │                         │
└──────────────────────────────┴─────────────────────────┘
    ↓
Context recall into future conversations

Personal Knowledge → separate approved document index
Runtime experience/state → memory/runtime/consciousness.json
```

Legacy `trinity_brain.json` files are local migration inputs only and are no longer active memory owners or version-controlled. Runtime-created SQLite/Vault state, runtime state, audit logs, backups, and local model artifacts stay outside Git and should be backed up locally. See `docs/RUNTIME_DATA.md` for the repository/runtime boundary.

Create a consistent memory backup:

```bash
python -m core.macos_deployment backup
```

Restore is deliberately approval-gated:

```bash
python -m core.macos_deployment restore /path/to/trinity-memory-YYYYMMDDTHHMMSSZ.tar.gz --approve
```

SQLite backups use the SQLite backup API so committed WAL data is included safely.

## Permissions and approvals

Trinity uses four action classes:

- **Safe** — read-only/local operations that can execute automatically.
- **Confirm** — side effects that pause and wait for explicit approval.
- **High risk** — sensitive system/security operations requiring stronger control.
- **Forbidden** — operations Trinity must not execute.

Unknown actions default to confirmation. When a confirm-level action is requested, Trinity can queue it and resume the exact action only after explicit approval. Saying `NO`/`CANCEL` clears the pending action without executing it.

## Voice

The intended local flow is:

```text
Microphone → local capture → local STT → Trinity → local TTS → speaker
```

The framework supports continuous local listening, wake-word/session handling, transient-error recovery, and interruption. Final microphone selection, Whisper size, TTS engine, and barge-in sensitivity should be tuned on the target Mac and room acoustics.

## Vision and screen awareness

Vision is local and provider-neutral. Screen awareness captures screenshots ephemerally, performs local multimodal analysis, and publishes textual awareness context. Raw screenshot bytes are not written into Trinity's action audit trail.

macOS Screen Recording permission is still enforced by macOS and must be granted manually.

## Computer control

Computer actions go through the shared permission engine and audit trail. Read-only observations can be safe; actions such as opening/activating applications, typing, clicking, shell execution, or other mutations remain confirmation/high-risk gated.

macOS Accessibility/Automation permission is required for supported desktop actions.

## Presence

Presence exposes Trinity's live state to a local visualizer:

```text
IDLE → LISTENING → THINKING → SEARCHING → TOOL_USE → EXECUTING → SPEAKING → DONE
                                                               ↘ ERROR
```

Presence is intended for localhost use and is not a second Trinity runtime.

## API and mobile access

The API is bound to the full Trinity instance. It cannot silently create a lightweight second brain.

Loopback is the safe default. LAN/VPN exposure requires proper authentication configuration; insecure remote binding is refused by policy. Prefer a trusted LAN or VPN and do not expose Ollama or the Memory Vault directly to the public Internet.

See `mobile/README.md` for the thin-client model.

## Interface routing

All user-facing text goes through `core/output.py` and the same `MessageService` pipeline. API/mobile requests bind their responder for the duration of a request, while local voice enters through the same `process_text` contract. Core reasoning does not know about a vendor-specific chat transport.

Phone access is provided through the authenticated local API/mobile client. Any future external connector must live behind the response/capability boundaries rather than adding transport logic to the Trinity composition root.

## Security guidance

- Never commit `.env`, API tokens, PINs, JWT secrets, model credentials, or private keys.
- Keep Ollama bound locally unless you deliberately secure remote access.
- Keep Presence local-only.
- Use the permission engine for every new side-effecting tool.
- Ensure audit metadata redacts secrets rather than serializing them.
- Keep raw audio/screenshots ephemeral unless the user explicitly chooses to persist them.
- Review generated/self-modifying code before approval; Trinity may draft improvements but must not silently persist them.

See `docs/SECURITY.md` for the detailed security model.

## Testing and validation

Run the full regression suite:

```bash
python -m pytest -q
```

Compile the active Python modules:

```bash
python -m compileall -q core voice skills agents
```

Architecture-contract tests guard against reintroducing cloud LLM dependencies, Git-based brain persistence, cloud runtime workflows, transport-specific coupling in core reasoning, or a standalone lightweight API brain.

At the time this final package was prepared, the working tree was validated with the complete regression suite before packaging. See `UPGRADE_STATUS.md` for the final verified count.

## Documentation index

- `deployment/macos/README.md` — complete Mac deployment and operations guide
- `docs/ARCHITECTURE.md` — architecture and data/control flow
- `docs/SECURITY.md` — security boundaries, permission model, and exposure guidance
- `docs/MAC_SETUP.md` — Mac commissioning checklist
- `ENGINEERING_ROADMAP.md` — future engineering work
- `UPGRADE_STATUS.md` — implementation/test status
- `ROADMAP.md` — broader Trinity6 roadmap/context

## Production commissioning still required on the physical Mac

The code architecture can be validated in CI/sandbox, but these items require the target hardware:

1. Benchmark final fast/general/reasoning/coding models on the M5 Pro 48 GB.
2. Choose/tune Whisper and TTS using the actual microphone, speakers, and room acoustics.
3. Choose/benchmark the final local multimodal vision model.
4. Grant and validate macOS Microphone, Accessibility, Automation, and Screen Recording permissions.
5. Validate mobile/API access on the intended LAN/VPN.
6. Validate launchd restart/recovery behavior on the real Mac.
7. Run multi-hour and multi-day soak tests for memory growth, logs, model stability, and hardware thermals.

---

**Trinity's identity and memory live with Trinity. The local model is a replaceable reasoning engine, not the owner of the system.**

## Pre-M5 Samsung test

If the Mac has not arrived yet, use [`ANDROID_START_HERE.md`](ANDROID_START_HERE.md) to run Trinity temporarily on a Samsung/Termux host with llama.cpp.
