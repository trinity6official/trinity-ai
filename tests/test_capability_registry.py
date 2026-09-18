from types import SimpleNamespace

from core.agent_runtime import AgentContract, AgentRegistry
from core.capabilities import CapabilityRegistry
from core.permissions import PermissionEngine, PermissionLevel


class FakeSkill:
    name = "demo"
    description = "Demonstration skill"

    def get_tools(self):
        return [
            {
                "name": "read_value",
                "description": "Read a value",
                "params": ["key"],
                "needs_approval": False,
            },
            {
                "name": "update_value",
                "description": "Update a value",
                "params": ["key", "value"],
                "needs_approval": True,
            },
        ]

    def execute(self, tool_name, params):
        return {"success": True}


class FakeSkills:
    def __init__(self):
        self.skill = FakeSkill()

    def _discover_skill_names(self):
        return ["demo"]

    def get_skill(self, name):
        return self.skill if name == "demo" else None

    def capability_requires_approval(self, skill_name, tool_name, *, skill=None):
        return tool_name == "update_value"


def _registry():
    agents = AgentRegistry()
    agents.register(
        "health",
        lambda ctx: "ok",
        action_type="health_checks",
        description="Check health",
        contract=AgentContract(allowed_data_keys=()),
    )
    registry = CapabilityRegistry(PermissionEngine(), skills=FakeSkills(), agents=agents)
    registry.register_runtime(
        "voice", "Local voice", lambda: True, interfaces=("voice", "conversation")
    )
    return registry


def test_registry_normalizes_skill_tool_permissions_and_interfaces():
    registry = _registry()
    read = registry.get("skill:demo.read_value")
    update = registry.get("skill:demo.update_value")
    assert read is not None and read.permission == PermissionLevel.SAFE
    assert read.execution_requires_approval is False
    assert "api" in read.interfaces
    assert update is not None and update.permission == PermissionLevel.CONFIRM
    assert update.execution_requires_approval is True


def test_registry_indexes_agents_without_becoming_execution_owner():
    registry = _registry()
    agent = registry.get("agent:health")
    assert agent is not None
    assert agent.kind == "agent"
    assert agent.permission == PermissionLevel.SAFE
    assert agent.metadata["action_type"] == "health_checks"
    assert agent.interfaces == ("runtime", "proactive")


def test_registry_filters_capabilities_by_interface():
    registry = _registry()
    api_ids = {item.capability_id for item in registry.list(interface="api")}
    voice_ids = {item.capability_id for item in registry.list(interface="voice")}
    assert "skill:demo.read_value" in api_ids
    assert "agent:health" not in api_ids
    assert "runtime:voice" in voice_ids


def test_registry_runtime_summary_uses_live_availability_probe():
    state = {"up": False}
    registry = CapabilityRegistry()
    registry.register_runtime(
        "vision", "Vision", lambda: state["up"], interfaces=("api",)
    )
    assert registry.runtime_summary()["vision"] is False
    state["up"] = True
    assert registry.runtime_summary()["vision"] is True


def test_registry_renders_prompt_blocks_from_tool_metadata():
    prompt = _registry().render_skill_blocks()
    assert "DEMO SKILL" in prompt
    assert "read_value(key) - Read a value" in prompt
    assert "update_value(key, value) - Update a value [NEEDS APPROVAL]" in prompt


def test_interface_manifest_is_serializable_plain_data():
    manifest = _registry().interface_manifest("api")
    assert manifest
    assert all(isinstance(item, dict) for item in manifest)
    assert all(isinstance(item["interfaces"], list) for item in manifest)


def test_bound_model_capability_is_false_when_health_fails_or_is_empty():
    class BrokenRouter:
        def health(self):
            raise RuntimeError("offline")

    runtime = SimpleNamespace(model_router=BrokenRouter())
    registry = CapabilityRegistry()
    registry.bind_runtime(runtime)
    assert registry.runtime_summary(interface="api")["local_ai"] is False

    runtime.model_router = SimpleNamespace(health=lambda: {})
    assert registry.runtime_summary(interface="api")["local_ai"] is False


def test_bound_voice_capability_reflects_real_provider_availability():
    local_voice = SimpleNamespace(can_speak=lambda: False, can_listen=lambda: False)
    runtime = SimpleNamespace(voice=SimpleNamespace(local_voice=local_voice))
    registry = CapabilityRegistry()
    registry.bind_runtime(runtime)
    assert registry.runtime_summary(interface="conversation")["voice"] is False

    local_voice.can_listen = lambda: True
    assert registry.runtime_summary(interface="conversation")["voice"] is True
