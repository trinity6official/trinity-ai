from core.agent_runtime import AgentContext, AgentRegistry
from core.execution import AgentExecutionRequest
from core.permissions import PermissionLevel


def test_safe_agent_runs_without_approval():
    registry = AgentRegistry()
    registry.register("health", lambda ctx: ctx.objective, action_type="health_checks")
    result = registry.execute("health", AgentContext("check system"))
    assert result.success is True
    assert result.output == "check system"
    assert result.permission == PermissionLevel.SAFE


def test_confirmation_agent_is_gated():
    registry = AgentRegistry()
    registry.register("client", lambda ctx: "sent", action_type="contacting_clients")
    result = registry.execute("client", AgentContext("contact prospect"))
    assert result.success is False
    assert result.requires_approval is True
    assert result.permission == PermissionLevel.CONFIRM


def test_confirmation_agent_runs_after_approval():
    registry = AgentRegistry()
    registry.register("client", lambda ctx: "sent", action_type="contacting_clients")
    result = registry.execute("client", AgentContext("contact prospect", approved=True))
    assert result.success is True
    assert result.output == "sent"


def test_forbidden_agent_never_runs():
    called = []
    registry = AgentRegistry()
    registry.register(
        "leak",
        lambda ctx: called.append(True),
        action_type="share_private_information",
    )
    result = registry.execute("leak", AgentContext("share secrets", approved=True))
    assert result.success is False
    assert called == []
    assert result.permission == PermissionLevel.FORBIDDEN


def test_unknown_agent_fails_cleanly():
    result = AgentRegistry().execute("missing", AgentContext("x"))
    assert result.success is False
    assert "Unknown agent" in result.error


def test_duplicate_registration_is_rejected():
    registry = AgentRegistry()
    registry.register("health", lambda ctx: None, action_type="health_checks")
    try:
        registry.register("health", lambda ctx: None, action_type="health_checks")
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Expected duplicate registration to fail")


def test_agent_contract_rejects_unexpected_input():
    from core.agent_runtime import AgentContract
    registry = AgentRegistry()
    registry.register(
        "draft", lambda ctx: ctx.data.get("topic"), action_type="content_generation",
        contract=AgentContract(allowed_data_keys=("topic",)),
    )
    result = registry.execute("draft", AgentContext("draft", {"path": "/tmp/x"}))
    assert result.success is False
    assert "violates contract" in result.error


def test_agent_contract_is_introspectable():
    from core.agent_runtime import AgentContract
    registry = AgentRegistry()
    registry.register(
        "health", lambda ctx: None, action_type="health_checks",
        contract=AgentContract(allowed_data_keys=(), network_access=True),
    )
    spec = registry.describe("health")
    assert spec.contract.allowed_data_keys == ()
    assert spec.contract.network_access is True


def test_agent_execute_request_is_authoritative_boundary():
    registry = AgentRegistry()
    registry.register("health", lambda ctx: ctx.data["scope"], action_type="health_checks")
    request = AgentExecutionRequest("HEALTH", "check", {"scope": "runtime"})
    result = registry.execute_request(request)
    assert result.success is True
    assert result.output == "runtime"
    assert request.agent == "health"


def test_agent_execution_request_and_handler_context_are_immutable():
    request = AgentExecutionRequest("health", "check", {"scope": "runtime"})
    try:
        request.data["scope"] = "changed"
    except TypeError:
        pass
    else:
        raise AssertionError("Agent request data must be immutable")

    context = AgentContext("check", {"scope": "runtime"})
    try:
        context.data["scope"] = "changed"
    except TypeError:
        pass
    else:
        raise AssertionError("Agent context data must be immutable")
