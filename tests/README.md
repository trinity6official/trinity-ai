# `tests/` — Trinity Validation Suite

Trinity reports confidence by test layer rather than by a single collected-test
count. The detailed policy is in `docs/TESTING_STRATEGY.md`.

Run everything:

```bash
python -m pytest -q
```

Focused architecture guardrails:

```bash
python -m pytest -q -m architecture
```

Focused contracts/integration/scenarios/failure paths:

```bash
python -m pytest -q -m "contract or integration or scenario or failure_path"
```

Important coverage areas include:

- local model routing and benchmarking
- memory migration/store/pipeline and restart persistence
- permissions, approval queue, execution boundary, and action auditing
- skills and agent contracts
- event bus/awareness/proactive scheduling
- voice sessions/runtime resilience
- vision and screen awareness privacy
- computer-control permission behavior
- API security and single-runtime binding
- macOS deployment/backup/restore
- runtime soak/failure isolation
- architecture debt budgets preventing known coupling from spreading

When adding a feature, add focused behavior plus boundary/failure coverage where
appropriate, then keep the full regression suite green.
