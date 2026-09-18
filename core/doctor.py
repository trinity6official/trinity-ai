"""Commissioning diagnostics for Trinity's local Mac runtime."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.ai_service import build_local_ai_from_environment
from core.api_security import DEFAULT_JWT_SECRET, validate_api_exposure
from core.macos_deployment import MacPreflight, PreflightReport


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[DiagnosticCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.ok for check in self.checks if check.required)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checks": [asdict(check) for check in self.checks],
        }


class TrinityDoctor:
    """Validate the pieces needed before enabling Trinity as an always-on service."""

    TASKS = ("fast", "general", "reasoning", "coding")

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        preflight: PreflightReport | None = None,
        stack_builder: Callable[[Mapping[str, str]], Any] = build_local_ai_from_environment,
    ) -> None:
        self.root = Path(project_root or Path(__file__).resolve().parent.parent).expanduser().resolve()
        self.env = dict(os.environ if environ is None else environ)
        self._preflight = preflight
        self.stack_builder = stack_builder

    @staticmethod
    def _enabled(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _memory_check(self) -> DiagnosticCheck:
        runtime_dir = self.root / "memory" / "runtime"
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix="doctor-", dir=runtime_dir, delete=False) as handle:
                path = Path(handle.name)
                handle.write(b"ok")
            path.unlink(missing_ok=True)
            return DiagnosticCheck("Memory Vault write", True, str(runtime_dir))
        except Exception as exc:
            return DiagnosticCheck("Memory Vault write", False, str(exc))

    def _api_check(self) -> DiagnosticCheck:
        host = self.env.get("TRINITY_API_HOST", "127.0.0.1")
        allowed, reason = validate_api_exposure(
            host,
            pin_hash=self.env.get("TRINITY_APP_PIN_HASH", ""),
            jwt_secret=self.env.get("TRINITY_JWT_SECRET", DEFAULT_JWT_SECRET),
            remote_transport=self.env.get("TRINITY_API_REMOTE_TRANSPORT", ""),
            tls_cert=self.env.get("TRINITY_API_TLS_CERT", ""),
            tls_key=self.env.get("TRINITY_API_TLS_KEY", ""),
            cors_origins=tuple(
                value.strip()
                for value in self.env.get("TRINITY_API_CORS", "*").split(",")
                if value.strip()
            ),
        )
        return DiagnosticCheck("API security", allowed, f"{host}: {reason}")

    def _voice_check(self) -> DiagnosticCheck:
        enabled = self._enabled(self.env.get("TRINITY_VOICE_LISTENING_ENABLED"), default=False)
        if not enabled:
            return DiagnosticCheck("Local voice listening", True, "disabled", required=False)
        whisper_available = importlib.util.find_spec("whisper") is not None
        detail = "Whisper package available" if whisper_available else "voice enabled but local Whisper is not installed"
        return DiagnosticCheck("Local voice listening", whisper_available, detail, required=False)

    def run(self) -> DoctorReport:
        checks: list[DiagnosticCheck] = []

        preflight = self._preflight or MacPreflight().run()
        checks.extend(
            DiagnosticCheck(item.name, item.ok, item.detail, item.required)
            for item in preflight.items
        )

        installed: set[str] = set()
        try:
            stack = self.stack_builder(self.env)
            checks.append(
                DiagnosticCheck(
                    "Ollama API",
                    bool(stack.ollama_available),
                    stack.base_url if stack.ollama_available else f"unreachable at {stack.base_url}",
                )
            )
            if stack.ollama_available:
                installed = {item.name for item in stack.router.available_models()}
                for task in self.TASKS:
                    candidates = stack.router.configured_models(task)
                    present = [model for model in candidates if model in installed]
                    checks.append(
                        DiagnosticCheck(
                            f"Model route: {task}",
                            bool(present),
                            (
                                f"available: {', '.join(present)}"
                                if present
                                else f"none installed from configured route: {', '.join(candidates)}"
                            ),
                        )
                    )
        except Exception as exc:
            checks.append(DiagnosticCheck("Local AI configuration", False, str(exc)))

        vision_model = self.env.get("TRINITY_VISION_MODEL", "").strip()
        if vision_model:
            checks.append(
                DiagnosticCheck(
                    "Vision model",
                    vision_model in installed,
                    (
                        f"installed: {vision_model}"
                        if vision_model in installed
                        else f"configured but not installed: {vision_model}"
                    ),
                    required=False,
                )
            )
        else:
            checks.append(DiagnosticCheck("Vision model", True, "not configured", required=False))

        checks.append(self._memory_check())
        checks.append(self._api_check())
        checks.append(self._voice_check())
        return DoctorReport(tuple(checks))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose Trinity local runtime readiness")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = TrinityDoctor().run()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        for check in report.checks:
            if check.ok:
                marker = "OK"
            elif check.required:
                marker = "FAIL"
            else:
                marker = "WARN"
            print(f"[{marker}] {check.name}: {check.detail}")
        print("READY" if report.ready else "NOT READY")
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
