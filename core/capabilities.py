"""Unified capability discovery and interface exposure for Trinity.

The registry is an index, not an execution engine. Skills remain owned by
``SkillManager`` and agents by ``AgentRegistry``; the registry normalizes their
metadata so prompts, status surfaces and APIs stop maintaining independent
capability lists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

from core.permissions import PermissionDecision, PermissionEngine, PermissionLevel


AvailabilityProbe = Callable[[], bool]


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Immutable normalized description of one Trinity capability."""

    capability_id: str
    kind: str
    owner: str
    name: str
    description: str = ""
    permission: PermissionLevel | None = None
    execution_requires_approval: bool = False
    interfaces: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    available: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", str(self.capability_id))
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "description", str(self.description or ""))
        object.__setattr__(self, "interfaces", tuple(str(v) for v in self.interfaces))
        object.__setattr__(self, "parameters", tuple(str(v) for v in self.parameters))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.capability_id,
            "kind": self.kind,
            "owner": self.owner,
            "name": self.name,
            "description": self.description,
            "permission": self.permission.value if self.permission is not None else None,
            "execution_requires_approval": self.execution_requires_approval,
            "interfaces": list(self.interfaces),
            "parameters": list(self.parameters),
            "available": self.available,
            "metadata": dict(self.metadata),
        }


class CapabilityRegistry:
    """Normalized discovery index for skills, agents and runtime interfaces."""

    USER_INTERFACES = ("conversation", "api", "mobile", "voice", "cli")
    AGENT_INTERFACES = ("runtime", "proactive")

    def __init__(
        self,
        permissions: PermissionEngine | None = None,
        *,
        skills: Any = None,
        agents: Any = None,
        mcp: Any = None,
    ) -> None:
        self.permissions = permissions or PermissionEngine()
        self.skills = skills
        self.agents = agents
        self.mcp = mcp
        self._runtime: dict[str, tuple[str, AvailabilityProbe, tuple[str, ...]]] = {}

    def bind_runtime(self, runtime: Any) -> None:
        """Register runtime feature probes without taking ownership of them."""

        def _model_available() -> bool:
            router = getattr(runtime, "model_router", None)
            if router is None:
                return False
            try:
                health = router.health()
            except Exception:
                return False
            return bool(health) and any(bool(value) for value in health.values())

        def _vision_available() -> bool:
            vision = getattr(runtime, "vision", None)
            return bool(vision and vision.available())

        def _computer_available() -> bool:
            computer = getattr(runtime, "computer", None)
            provider = getattr(computer, "provider", None) if computer is not None else None
            return bool(provider and provider.available())

        self.register_runtime(
            "runtime_bound", "Full Trinity runtime is bound to this interface",
            lambda: True, interfaces=("api", "mobile"),
        )
        self.register_runtime(
            "local_ai", "Provider-neutral local model router",
            _model_available, interfaces=self.USER_INTERFACES,
        )
        self.register_runtime(
            "memory", "Authoritative local MemoryService and MemoryStore",
            lambda: hasattr(runtime, "memory_store"), interfaces=self.USER_INTERFACES,
        )
        def _voice_available() -> bool:
            voice = getattr(runtime, "voice", None)
            local_voice = getattr(voice, "local_voice", None) if voice is not None else None
            if local_voice is None:
                return False
            try:
                return bool(local_voice.can_speak() or local_voice.can_listen())
            except Exception:
                return False

        self.register_runtime(
            "voice", "Local speech input and output",
            _voice_available, interfaces=("voice", "conversation"),
        )
        self.register_runtime(
            "vision", "Local multimodal vision",
            _vision_available, interfaces=self.USER_INTERFACES,
        )
        self.register_runtime(
            "computer_control", "Permission-gated local computer control",
            _computer_available, interfaces=self.USER_INTERFACES,
        )
        self.register_runtime(
            "message_pipeline", "Shared channel-neutral message pipeline",
            lambda: hasattr(runtime, "messages") or callable(getattr(runtime, "process_text", None)),
            interfaces=self.USER_INTERFACES,
        )

    def register_runtime(
        self,
        name: str,
        description: str,
        available: AvailabilityProbe,
        *,
        interfaces: tuple[str, ...],
    ) -> None:
        key = str(name).strip().lower()
        if not key:
            raise ValueError("Runtime capability name cannot be empty")
        self._runtime[key] = (str(description), available, tuple(interfaces))

    def _skill_names(self) -> list[str]:
        if self.skills is None:
            return []
        discover = getattr(self.skills, "_discover_skill_names", None)
        if callable(discover):
            return list(discover())
        return list(self.skills.list_available_skills())

    def _skill_descriptors(self) -> list[CapabilityDescriptor]:
        descriptors: list[CapabilityDescriptor] = []
        if self.skills is None:
            return descriptors

        for skill_name in self._skill_names():
            skill = self.skills.get_skill(skill_name)
            if skill is None:
                continue
            getter = getattr(skill, "get_tools", None)
            execute = getattr(skill, "execute", None)
            if not callable(getter) or not callable(execute):
                continue
            try:
                tools = getter()
            except Exception:
                continue
            if not isinstance(tools, list):
                continue
            skill_description = str(getattr(skill, "description", "") or "")
            for tool in tools:
                if not isinstance(tool, dict) or not tool.get("name"):
                    continue
                tool_name = str(tool["name"]).strip()
                decision = self.permissions.assess_tool(skill_name, tool_name)
                gate = getattr(self.skills, "capability_requires_approval", None)
                if callable(gate):
                    requires_approval = bool(gate(skill_name, tool_name, skill=skill))
                else:
                    requires_approval = decision.requires_confirmation
                metadata = {
                    "declared_needs_approval": bool(tool.get("needs_approval", False)),
                    "skill_description": skill_description,
                }
                descriptors.append(
                    CapabilityDescriptor(
                        capability_id=f"skill:{skill_name}.{tool_name}",
                        kind="skill_tool",
                        owner=skill_name,
                        name=tool_name,
                        description=str(tool.get("description", "") or ""),
                        permission=decision.level,
                        execution_requires_approval=requires_approval,
                        interfaces=self.USER_INTERFACES,
                        parameters=tuple(tool.get("params") or ()),
                        available=True,
                        metadata=metadata,
                    )
                )
        return descriptors

    def _agent_descriptors(self) -> list[CapabilityDescriptor]:
        descriptors: list[CapabilityDescriptor] = []
        if self.agents is None:
            return descriptors
        for name in self.agents.names():
            spec = self.agents.describe(name)
            decision: PermissionDecision = self.agents.permission_for(name)
            descriptors.append(
                CapabilityDescriptor(
                    capability_id=f"agent:{name}",
                    kind="agent",
                    owner="agent_registry",
                    name=name,
                    description=spec.description,
                    permission=decision.level,
                    execution_requires_approval=decision.requires_confirmation,
                    interfaces=self.AGENT_INTERFACES,
                    available=True,
                    metadata={
                        "action_type": spec.action_type,
                        "network_access": spec.contract.network_access,
                        "memory_access": spec.contract.memory_access,
                        "side_effects": spec.contract.side_effects,
                        "allowed_data_keys": (
                            list(spec.contract.allowed_data_keys)
                            if spec.contract.allowed_data_keys is not None else None
                        ),
                    },
                )
            )
        return descriptors


    def _mcp_descriptors(self) -> list[CapabilityDescriptor]:
        """Normalize cached MCP discoveries without starting servers or performing I/O."""
        manager = self.mcp
        if manager is None:
            return []
        cached = getattr(manager, "cached_tools", None)
        health = getattr(manager, "health", None)
        if not callable(cached):
            return []
        try:
            tools = tuple(cached())
        except Exception:
            return []

        descriptors: list[CapabilityDescriptor] = []
        for tool in tools:
            server = str(getattr(tool, "server", "") or "").strip()
            name = str(getattr(tool, "name", "") or "").strip()
            if not server or not name:
                continue
            available = False
            if callable(health):
                try:
                    state = health(server)
                    available = bool(
                        getattr(state, "running", False)
                        and getattr(state, "initialized", False)
                    )
                except Exception:
                    available = False
            schema = dict(getattr(tool, "input_schema", {}) or {})
            properties = schema.get("properties", {}) or {}
            parameters = tuple(properties) if isinstance(properties, Mapping) else ()
            try:
                config = manager.config(server)
                enabled = bool(config.execution_enabled)
                allowlisted = name in config.allowed_tools
                trust = config.trust
            except Exception:
                enabled = False
                allowlisted = False
                trust = "untrusted"
            decision = self.permissions.assess_mcp_tool(
                server, name, server_trust=trust
            )
            executable = enabled and allowlisted
            interfaces = self.USER_INTERFACES if executable else ("runtime",)
            descriptors.append(
                CapabilityDescriptor(
                    capability_id=f"mcp:{server}.{name}",
                    kind="mcp_tool",
                    owner=f"mcp:{server}",
                    name=name,
                    description=str(getattr(tool, "description", "") or ""),
                    permission=decision.level,
                    execution_requires_approval=decision.requires_confirmation,
                    interfaces=interfaces,
                    parameters=parameters,
                    available=available,
                    metadata={
                        "server": server,
                        "input_schema": schema,
                        "execution_enabled": enabled,
                        "allowlisted": allowlisted,
                        "server_trust": trust,
                        "governance": "active" if executable else "disabled",
                    },
                )
            )
        return descriptors

    def _runtime_descriptors(self) -> list[CapabilityDescriptor]:
        result: list[CapabilityDescriptor] = []
        for name, (description, probe, interfaces) in self._runtime.items():
            try:
                available = bool(probe())
            except Exception:
                available = False
            result.append(
                CapabilityDescriptor(
                    capability_id=f"runtime:{name}",
                    kind="runtime",
                    owner="runtime",
                    name=name,
                    description=description,
                    interfaces=interfaces,
                    available=available,
                )
            )
        return result

    def list(
        self,
        *,
        interface: str | None = None,
        kind: str | None = None,
        include_unavailable: bool = True,
    ) -> tuple[CapabilityDescriptor, ...]:
        descriptors = (
            self._skill_descriptors()
            + self._agent_descriptors()
            + self._mcp_descriptors()
            + self._runtime_descriptors()
        )
        if interface is not None:
            descriptors = [d for d in descriptors if interface in d.interfaces]
        if kind is not None:
            descriptors = [d for d in descriptors if d.kind == kind]
        if not include_unavailable:
            descriptors = [d for d in descriptors if d.available]
        return tuple(sorted(descriptors, key=lambda d: d.capability_id))

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        wanted = str(capability_id)
        return next((item for item in self.list() if item.capability_id == wanted), None)

    def skill_names(self, *, interface: str = "conversation") -> list[str]:
        names = {
            item.owner
            for item in self.list(interface=interface, kind="skill_tool", include_unavailable=False)
        }
        return sorted(names)

    def runtime_summary(self, *, interface: str = "api") -> dict[str, bool]:
        return {
            item.name: item.available
            for item in self.list(interface=interface, kind="runtime")
        }

    def interface_manifest(self, interface: str) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.list(interface=interface)]

    def render_skill_blocks(self, *, skills: list[str] | None = None) -> str:
        """Render tool metadata for the model prompt from the normalized registry."""
        selected = set(skills) if skills is not None else set(self.skill_names())
        grouped: dict[str, list[CapabilityDescriptor]] = {}
        for item in self.list(interface="conversation", kind="skill_tool", include_unavailable=False):
            if item.owner in selected:
                grouped.setdefault(item.owner, []).append(item)

        blocks: list[str] = []
        for skill_name in sorted(grouped):
            tools = grouped[skill_name]
            purpose = str(tools[0].metadata.get("skill_description", "") or "")
            lines = [f"{skill_name.upper()} SKILL", f"Purpose: {purpose}", "Tools:"]
            for item in sorted(tools, key=lambda value: value.name):
                params = ", ".join(item.parameters)
                approval = (
                    " [NEEDS APPROVAL]"
                    if item.execution_requires_approval
                    or bool(item.metadata.get("declared_needs_approval"))
                    else ""
                )
                lines.append(
                    f"  {item.name}({params}) - {item.description}{approval}"
                )
            blocks.append("\n".join(lines))

        mcp_grouped: dict[str, list[CapabilityDescriptor]] = {}
        for item in self.list(interface="conversation", kind="mcp_tool", include_unavailable=False):
            if not item.metadata.get("execution_enabled") or not item.metadata.get("allowlisted"):
                continue
            server = str(item.metadata.get("server", ""))
            mcp_grouped.setdefault(server, []).append(item)
        for server in sorted(mcp_grouped):
            lines = [f"MCP SERVER: {server}", "External tools (governed by Trinity permissions):"]
            for item in sorted(mcp_grouped[server], key=lambda value: value.name):
                params = ", ".join(item.parameters)
                approval = " [NEEDS APPROVAL]" if item.execution_requires_approval else ""
                lines.append(f"  {item.name}({params}) - {item.description}{approval}")
            lines.extend(["Call format:", f"  MCP_CALL: {server}.{mcp_grouped[server][0].name}"])
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
