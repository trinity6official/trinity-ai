from types import SimpleNamespace

from core.agent_bootstrap import build_default_agent_registry
from core.permissions import PermissionLevel


def _memory():
    return SimpleNamespace(
        brain={"company": {"clients": [], "revenue": 0}, "david": {}},
        save=lambda: None,
        add_daily_log=lambda *a, **k: None,
    )


def test_default_agents_have_explicit_contracts():
    registry = build_default_agent_registry(memory=_memory(), llm=None, gh_token=None)
    assert registry.describe("business_status").contract.memory_access == "read"
    assert registry.describe("github_monitor").contract.network_access is True
    assert registry.describe("content_draft").contract.allowed_data_keys == ("topic",)
    assert registry.describe("security_scan").contract.side_effects == "network-scan"


def test_security_scan_requires_confirmation_before_handler_runs():
    registry = build_default_agent_registry(memory=_memory(), llm=None, gh_token=None)
    result = registry.execute("security_scan", __import__('core.agent_runtime', fromlist=['AgentContext']).AgentContext("scan"))
    assert result.requires_approval is True
    assert result.permission == PermissionLevel.CONFIRM
