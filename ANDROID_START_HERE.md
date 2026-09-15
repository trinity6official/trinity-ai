# Start Trinity on the Samsung S24 Ultra

This is a temporary pre-M5 test build. It does not replace Trinity's Mac architecture.

1. Install **Termux** and **Termux:API** from the same source (F-Droid or the Termux GitHub releases).
2. Download and extract this Trinity package on the S24, then open Termux and `cd` into the project folder.
3. Run:

```bash
./scripts/install_android_test.sh
```

4. In Termux session 1, start the local model:

```bash
./scripts/start_android_model.sh
```

The first run downloads the official Qwen3 4B Q4_K_M GGUF (~2.5 GB).

5. Open Termux session 2 in the Trinity folder:

```bash
python -m core.android_test --check
python -m core.android_test
```

Inside Trinity:

- `/speak` — Trinity speaks replies
- `/voice` — speak your next input
- `/text` — return to typing
- `/status` — check model/voice readiness
- `/quit` — exit

First test:

> Remember that my Samsung S24 Ultra is only my temporary Trinity test device.

Exit Trinity, restart it, then ask:

> What device did I say is my temporary Trinity test device?

If it recalls the answer, you have tested the local model + Trinity conversation + persistent memory together.

Vision/macOS computer control are not part of this phone phase; those are tested on the M5 later.
