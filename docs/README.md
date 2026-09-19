# `docs/` — Trinity Documentation

Project-wide documentation belongs here. Subsystem/operator READMEs may remain beside the code they document when that keeps implementation and operating instructions together.

## Authoritative project state

- `PROJECT_STATUS.md` — **single source of truth** for completed Trinity AI engineering work, final pre-hardware readiness, verification results, deferred non-blocking debt, and M6 hardware commissioning results.

## Stable reference documents

- `ARCHITECTURE.md` — runtime architecture, ownership boundaries, and control/data flow.
- `SECURITY.md` — trust, approval provenance, permission model, secrets, and network exposure.
- `TESTING_STRATEGY.md` — test layers and deterministic regression policy.
- `RUNTIME_DATA.md` — repository/runtime-state boundary.
- `MAC_SETUP.md` — operational checklist for commissioning the target Mac mini M6 32 GB.
- `ANDROID_PRE_HARDWARE_TEST.md` — temporary Samsung/Termux acceptance workflow before the M6 arrives.
- `PERSONAL_KNOWLEDGE.md` — personal-knowledge subsystem guidance.
- `SESSION_MEMORY.md` — session-memory guidance.
- `TRINITY6_BUSINESS_ROADMAP.md` — broader Trinity6 business roadmap; intentionally separate from Trinity AI runtime engineering status.

The detailed macOS deployment/operations guide remains in `deployment/macos/README.md` because it is maintained alongside the deployment scripts.

Do not create additional project-wide progress/status documents. Update `PROJECT_STATUS.md` instead.
