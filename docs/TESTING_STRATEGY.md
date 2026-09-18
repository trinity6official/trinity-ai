# Trinity Testing Strategy

Trinity's test suite is a safety net, not proof that the architecture is healthy.
The project therefore reports confidence by **test layer**, not by a single test
count.

## Confidence layers

1. **Unit / behavior tests** — focused behavior of individual modules.
2. **Contract tests** — stable guarantees at important boundaries such as
   permissions, memory, model providers, and future capabilities.
3. **Integration tests** — real Trinity components wired together with temporary
   local storage. External nondeterministic systems may be replaced by small
   deterministic fakes.
4. **Scenario tests** — exercise a meaningful request or action path across
   multiple internal boundaries.
5. **Failure-path tests** — verify denial, exceptions, restart, persistence,
   timeout/cancellation, and recovery behavior.
6. **Architecture tests** — enforce dependency direction and prevent known
   architecture debt from spreading while it is being removed.

The full regression suite still runs after the focused safety suites.

## Mocking policy

Mocks are acceptable for narrow unit tests. New contract/integration/scenario
coverage should prefer real internal Trinity components and temporary SQLite/
filesystem state. Fake only boundaries that are genuinely external or
nondeterministic (for example an LLM or remote API).

A green unit suite cannot compensate for a missing integration contract.

## Architecture debt budgets

Known architecture debt is tracked as enforceable maximums rather than informal
intent. The retired remote-chat transport and retired direct-writing skill-builder
path now have **zero-coupling invariants** in active application code. Legacy JSON
references remain confined to migration/backup boundaries while later consolidation
work continues to shrink the remaining budgets.

This lets consolidation proceed incrementally without pretending the current
architecture is the target architecture.

## Refactor rule

For architecture changes:

1. characterize current behavior at the relevant boundary;
2. add the target invariant or contract;
3. refactor behind that boundary;
4. add failure/restart coverage where state or side effects are involved;
5. run focused suites and then the complete regression suite.

## Commands

Focused architecture guardrails:

```bash
python -m pytest -q -m architecture
```

Focused contracts and real integration scenarios:

```bash
python -m pytest -q -m "contract or integration or scenario or failure_path"
```

Full regression:

```bash
python -m pytest -q
```
