"""Compatibility entry point for Trinity with the local HTTP API enabled.

The API is no longer a second brain/process. The modern Trinity lifecycle owns
an in-process :class:`core.api_runtime.LocalAPIServer` and binds it to the same
runtime used by local voice, Presence and optional Telegram remote chat.

Prefer ``python -m core.run`` for new deployments. This module remains so older
launch scripts continue to work.
"""
from __future__ import annotations

import os
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    os.environ.setdefault("TRINITY_API_ENABLED", "true")
    from core.run import main as run_main

    return run_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
