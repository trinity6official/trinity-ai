# `tests/` — Trinity Validation Suite

The test suite covers unit behavior, integration boundaries, resilience, security, deployment, and architecture contracts.

Run everything:

```bash
python -m pytest -q
```

Important coverage areas include:

- local model routing and benchmarking
- memory migration/store/pipeline
- permissions, approval queue, and action auditing
- skills and agent contracts
- event bus/awareness/proactive scheduling
- voice sessions/runtime resilience
- vision and screen awareness privacy
- computer-control permission behavior
- API security and single-runtime binding
- Telegram channel isolation
- macOS deployment/backup/restore
- runtime soak/failure isolation
- architecture-contract tests preventing cloud-runtime regressions

When adding a feature, add focused tests and keep architecture-contract tests green.
