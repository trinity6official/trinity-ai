from types import SimpleNamespace
from unittest.mock import MagicMock

from core.status_service import StatusService


def _host():
    consciousness = MagicMock()
    consciousness.get_memory_stats.return_value = {
        "total_boots": 2,
        "total_actions": 9,
        "decisions_logged": 3,
        "episodic_count": 4,
        "semantic_count": 5,
        "procedural_count": 6,
        "working_count": 2,
        "patterns_detected": 1,
    }
    consciousness.get_state.return_value = {
        "mood": "focused", "confidence": 0.9, "energy": 0.8,
        "current_focus": "tests",
    }
    consciousness.brain = {"patterns": []}
    consciousness.get_recent_failures.return_value = []
    memory = MagicMock(); memory.get_days_alive.return_value = 10
    memory.get_current_focus.return_value = None
    skills = MagicMock()
    return SimpleNamespace(
        consciousness=consciousness,
        memory=memory,
        skills=skills,
        daemon=None,
        runtime_mode=SimpleNamespace(value="local_interactive"),
        _local_model_name="local-test-model",
        respond=MagicMock(),
    )


def test_send_help_uses_channel_and_returns_message():
    host = _host()
    message = StatusService(host).send_help("english")
    assert "Trinity Commands" in message
    host.respond.assert_called_once_with(message)


def test_send_status_describes_local_runtime_without_github_actions_mode():
    host = _host()
    service = StatusService(host)
    service.health_summary = MagicMock(return_value={"skills_loaded": 8, "website_live": True})
    message = service.send_status()
    assert "Local Interactive" in message
    assert "GitHub Actions" not in message
    host.respond.assert_called_once_with(message)


def test_send_brain_status_contains_memory_counts():
    host = _host()
    message = StatusService(host).send_brain_status()
    assert "Episodic: 4 memories" in message
    assert "Confidence: 90%" in message

def test_help_exposes_objective_controls():
    host = _host()
    message = StatusService(host).send_help("english")
    assert "/objectives" in message
    assert "/objective" in message


def test_brain_status_separates_runtime_and_objective_focus():
    host = _host()
    host.memory.get_current_focus.return_value = {
        "id": "abcdef123456",
        "title": "Ship Trinity",
    }

    message = StatusService(host).send_brain_status()

    assert "Runtime Focus: tests" in message
    assert "Objective Focus: Ship Trinity [abcdef12]" in message
