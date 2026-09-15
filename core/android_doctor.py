"""Pre-hardware readiness checks for Trinity running in Android/Termux."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.ai_service import build_local_ai_from_environment


@dataclass(frozen=True)
class AndroidCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class AndroidDoctorReport:
    checks: tuple[AndroidCheck, ...]

    @property
    def ready(self) -> bool:
        return all(item.ok for item in self.checks if item.required)

    def to_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "checks": [asdict(item) for item in self.checks]}


class AndroidTrinityDoctor:
    def __init__(self, root: str | Path | None = None, *, environ: Mapping[str, str] | None = None):
        self.root = Path(root or Path(__file__).resolve().parent.parent).resolve()
        self.env = dict(os.environ if environ is None else environ)

    def _command(self, name: str, *, required: bool) -> AndroidCheck:
        path = shutil.which(name)
        if not path and name == "llama-server":
            candidate = Path(self.env.get("HOME", str(Path.home()))) / "llama.cpp" / "build" / "bin" / "llama-server"
            if candidate.exists():
                path = str(candidate)
        return AndroidCheck(name, bool(path), path or "not found", required=required)

    def run(self) -> AndroidDoctorReport:
        checks = [
            AndroidCheck("Termux environment", "com.termux" in self.env.get("PREFIX", "") or bool(self.env.get("TERMUX_VERSION")), self.env.get("PREFIX", "Termux marker not detected")),
            self._command("python", required=True),
            self._command("llama-server", required=True),
            self._command("termux-tts-speak", required=False),
            self._command("termux-speech-to-text", required=False),
        ]
        config = self.root / "config" / "android_test.yaml"
        checks.append(AndroidCheck("Android Trinity profile", config.exists(), str(config)))
        memory = self.root / "memory" / "runtime"
        try:
            memory.mkdir(parents=True, exist_ok=True)
            probe = memory / ".android-doctor"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            checks.append(AndroidCheck("Memory write", True, str(memory)))
        except OSError as exc:
            checks.append(AndroidCheck("Memory write", False, str(exc)))

        if config.exists():
            env = dict(self.env)
            env["TRINITY_LOCAL_AI_CONFIG"] = str(config)
            try:
                stack = build_local_ai_from_environment(env)
                checks.append(AndroidCheck("llama.cpp API", stack.provider_available, stack.base_url))
                if stack.provider_available:
                    installed = {item.name for item in stack.router.available_models()}
                    wanted = stack.router.configured_models("general")
                    checks.append(AndroidCheck("Phone model", any(m in installed for m in wanted), f"configured={','.join(wanted)} installed={','.join(sorted(installed)) or 'none'}"))
            except Exception as exc:
                checks.append(AndroidCheck("Local AI", False, str(exc)))
        return AndroidDoctorReport(tuple(checks))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Trinity Android/Termux test readiness")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = AndroidTrinityDoctor().run()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for item in report.checks:
            marker = "OK" if item.ok else ("FAIL" if item.required else "WARN")
            print(f"[{marker}] {item.name}: {item.detail}")
        print("READY" if report.ready else "NOT READY")
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
