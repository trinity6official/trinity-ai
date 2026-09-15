"""Runtime-mode detection for Trinity."""
from __future__ import annotations

import os
from enum import Enum


class RuntimeMode(str, Enum):
    LOCAL_DAEMON = "local_daemon"
    LOCAL_ONESHOT = "local_oneshot"
    CI = "ci"

    @property
    def is_daemon(self) -> bool:
        return self == RuntimeMode.LOCAL_DAEMON


def detect_runtime(env: dict[str, str] | None = None) -> RuntimeMode:
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS", "").lower() == "true" or env.get("CI"):
        return RuntimeMode.CI
    if env.get("TRINITY_ONESHOT", "").lower() in {"1", "true", "yes"}:
        return RuntimeMode.LOCAL_ONESHOT
    return RuntimeMode.LOCAL_DAEMON
