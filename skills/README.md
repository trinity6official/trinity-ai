# `skills/` — Trinity Skills

Skills are dynamically discoverable tools invoked by Trinity through `core/skill_manager.py`.

Examples include calculator, code, search, web, memory, GitHub, business, computer control, consciousness access, and debug helpers.

## Execution contract

```text
Conversation request
    ↓
SkillManager
    ↓
PermissionEngine
    ↓
ActionAudit
    ↓
Skill execution
    ↓
Result → Conversation
```

Read-only analysis may be classified as safe. Mutating or sensitive actions must require confirmation/high-risk handling. Skill-building/self-improvement is not a normal executable skill: missing capabilities are drafted through `core/skill_evolution.py`, held as proposals, and may write or persist generated code only after explicit approval.

When adding a skill, include focused tests and ensure unknown actions do not accidentally default to autonomous execution.
