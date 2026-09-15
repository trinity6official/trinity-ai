"""Loopback-only API launcher for the temporary Android pre-hardware test.

This does not change Trinity's production architecture.  It binds the existing
FastAPI app to the AndroidTestRuntime so the Flutter client can exercise the
real PIN -> JWT -> authenticated chat flow on one S24.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.android_test import AndroidTestRuntime


class AndroidApiAdapter:
    """Expose the tiny compatibility surface expected by core.api_bridge."""

    def __init__(self, runtime: AndroidTestRuntime) -> None:
        self.runtime = runtime
        self.memory_store = runtime.memory
        self.voice = runtime.voice
        self.model_router = runtime.stack.router

    def ask_trinity(self, text: str) -> str:
        return self.runtime.ask(text)


def main() -> int:
    if not os.environ.get("TRINITY_APP_PIN_HASH"):
        raise SystemExit("TRINITY_APP_PIN_HASH is required")
    if len(os.environ.get("TRINITY_JWT_SECRET", "")) < 32:
        raise SystemExit("TRINITY_JWT_SECRET must be at least 32 characters")

    # Import after security environment variables are present because core.api
    # intentionally snapshots auth configuration at import time.
    import uvicorn
    from core import api

    root = Path(__file__).resolve().parent.parent
    runtime = AndroidTestRuntime(root)
    if not runtime.stack.provider_available:
        raise SystemExit(
            "llama.cpp is not reachable on 127.0.0.1:8080. Start the phone model first."
        )

    api.set_runtime_brain(AndroidApiAdapter(runtime))
    print("Trinity Mobile test API: http://127.0.0.1:8000")
    print("Loopback only. Press Ctrl+C to stop.")
    uvicorn.run(api.app, host="127.0.0.1", port=8000, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
