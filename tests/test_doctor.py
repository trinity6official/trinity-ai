from types import SimpleNamespace

from core.doctor import TrinityDoctor
from core.macos_deployment import PreflightItem, PreflightReport
from core.models import ModelInfo


class FakeRouter:
    def __init__(self):
        self.routes = {
            "fast": ("fast-model",),
            "general": ("general-model", "fallback-model"),
            "reasoning": ("reason-model",),
            "coding": ("code-model",),
        }

    def available_models(self):
        return [
            ModelInfo("fast-model", "fake"),
            ModelInfo("general-model", "fake"),
            ModelInfo("reason-model", "fake"),
            ModelInfo("code-model", "fake"),
            ModelInfo("vision-model", "fake"),
        ]

    def configured_models(self, task):
        return self.routes[task]


def _stack(_env):
    return SimpleNamespace(
        ollama_available=True,
        base_url="http://127.0.0.1:11434",
        router=FakeRouter(),
    )


def _preflight(ok=True):
    return PreflightReport((
        PreflightItem("macOS", ok, "Darwin" if ok else "Linux"),
        PreflightItem("Ollama", ok, "/opt/homebrew/bin/ollama" if ok else "not found"),
    ))


def test_doctor_reports_ready_for_complete_local_stack(tmp_path):
    report = TrinityDoctor(
        tmp_path,
        environ={
            "TRINITY_API_HOST": "127.0.0.1",
            "TRINITY_VISION_MODEL": "vision-model",
        },
        preflight=_preflight(),
        stack_builder=_stack,
    ).run()
    assert report.ready is True
    assert next(c for c in report.checks if c.name == "Model route: coding").ok is True
    assert next(c for c in report.checks if c.name == "Vision model").ok is True


def test_doctor_fails_when_required_model_route_is_missing(tmp_path):
    def bad_stack(_env):
        stack = _stack(_env)
        stack.router.routes["reasoning"] = ("missing-model",)
        return stack

    report = TrinityDoctor(
        tmp_path,
        environ={},
        preflight=_preflight(),
        stack_builder=bad_stack,
    ).run()
    assert report.ready is False
    reasoning = next(c for c in report.checks if c.name == "Model route: reasoning")
    assert reasoning.ok is False


def test_doctor_flags_insecure_remote_api_binding(tmp_path):
    report = TrinityDoctor(
        tmp_path,
        environ={"TRINITY_API_HOST": "0.0.0.0"},
        preflight=_preflight(),
        stack_builder=_stack,
    ).run()
    assert report.ready is False
    api = next(c for c in report.checks if c.name == "API security")
    assert api.ok is False


def test_doctor_checks_are_local_runtime_dependencies(tmp_path):
    report = TrinityDoctor(
        tmp_path,
        environ={"TRINITY_API_HOST": "127.0.0.1"},
        preflight=_preflight(),
        stack_builder=_stack,
    ).run()
    names = {check.name for check in report.checks}
    assert "API security" in names
    assert "Local voice listening" in names
    assert all("remote chat" not in name.lower() for name in names)
