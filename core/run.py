"""Trinity AI local runtime entry point.

The Mac is Trinity's primary runtime. The HTTP API, mobile clients, local voice,
and Presence all bind to the same :class:`core.trinity.Trinity` instance.
CI/one-shot mode performs a clean boot/shutdown validation only; it never
commits or pushes Trinity's memory to Git.

Usage:
    python -m core.run
    python -m core.run --mode daemon
    python -m core.run --mode oneshot
    python -m core.run --mode ci

``actions`` is retained as a compatibility alias for ``ci`` but no longer
implements the old GitHub-Actions consciousness loop.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import Any

from core.runtime import RuntimeMode, detect_runtime


_MODE_ALIASES = {
    "daemon": RuntimeMode.LOCAL_DAEMON,
    "oneshot": RuntimeMode.LOCAL_ONESHOT,
    "ci": RuntimeMode.CI,
    "actions": RuntimeMode.CI,
}


def resolve_mode(requested: str = "auto") -> RuntimeMode:
    """Resolve a CLI mode without duplicating environment detection rules."""
    if requested == "auto":
        return detect_runtime()
    try:
        return _MODE_ALIASES[requested]
    except KeyError as exc:
        raise ValueError(f"Unknown Trinity runtime mode: {requested}") from exc


def run_runtime(
    mode: RuntimeMode,
    *,
    trinity_factory: Callable[[], Any] | None = None,
) -> int:
    """Run one modern Trinity instance in the requested mode.

    Daemon mode delegates to Trinity's RuntimeLoop. CI/one-shot modes are
    intentionally side-effect-light: initialize the complete local stack,
    record the selected runtime mode, then use Trinity's normal shutdown path.
    """
    if trinity_factory is None:
        from core.trinity import Trinity

        trinity_factory = Trinity

    trinity = trinity_factory()
    trinity.runtime_mode = mode

    if mode == RuntimeMode.LOCAL_DAEMON:
        trinity.run()
        return 0

    events = getattr(trinity, "events", None)
    if events is not None:
        events.publish("runtime.oneshot", mode=mode.value)

    shutdown = getattr(trinity, "_shutdown", None)
    if callable(shutdown):
        shutdown()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trinity AI local runtime")
    parser.add_argument(
        "--mode",
        choices=["auto", "daemon", "oneshot", "ci", "actions"],
        default="auto",
        help="Runtime mode (default: auto-detect)",
    )
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode)
    print(f"[TRINITY] Runtime mode: {mode.value}")
    return run_runtime(mode)


if __name__ == "__main__":
    raise SystemExit(main())
