"""Registration of Trinity's existing domain agents into the unified runtime."""
from __future__ import annotations

from agents.business_agent import BusinessAgent
from agents.content_agent import ContentAgent
from agents.github_agent import GitHubAgent
from agents.security_agent import SecurityAgent
from core.agent_runtime import AgentContract, AgentRegistry
from core.permissions import PermissionEngine
from core.audit import ActionAuditTrail


def build_default_agent_registry(
    *,
    memory=None,
    llm=None,
    gh_token: str | None = None,
    permissions: PermissionEngine | None = None,
    audit_trail: ActionAuditTrail | None = None,
) -> AgentRegistry:
    registry = AgentRegistry(permissions=permissions, audit_trail=audit_trail)

    business = BusinessAgent(memory=memory, llm=llm)
    content = ContentAgent(memory=memory, llm=llm)
    github = GitHubAgent(gh_token=gh_token)
    security = SecurityAgent(memory=memory)

    registry.register(
        "business_status",
        lambda ctx: business.get_business_status(),
        action_type="monitoring_checks",
        description="Read Trinity6 business health and pipeline status.",
        contract=AgentContract(
            allowed_data_keys=(), memory_access="read", side_effects="none"
        ),
    )
    registry.register(
        "github_monitor",
        lambda ctx: github.check_all_repos(),
        action_type="monitoring_checks",
        description="Read repository status across Trinity6 projects.",
        contract=AgentContract(
            allowed_data_keys=(), network_access=True, memory_access="none",
            side_effects="external-read",
        ),
    )
    registry.register(
        "content_draft",
        lambda ctx: content.generate_linkedin_post(ctx.data.get("topic")),
        action_type="content_generation",
        description="Generate a draft locally; publishing is a separate approval-gated action.",
        contract=AgentContract(
            allowed_data_keys=("topic",), memory_access="read", side_effects="none"
        ),
    )
    registry.register(
        "security_scan",
        lambda ctx: security.run_security_check(),
        action_type="network_scanning",
        description="Actively scan the local network and security posture.",
        contract=AgentContract(
            allowed_data_keys=(), network_access=True, memory_access="read",
            side_effects="network-scan",
        ),
    )
    return registry
