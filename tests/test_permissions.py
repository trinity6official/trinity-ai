from core.permissions import PermissionEngine, PermissionLevel


def test_known_safe_action_is_autonomous():
    decision = PermissionEngine().assess_action("morning_briefing")
    assert decision.level == PermissionLevel.SAFE
    assert decision.allowed_autonomously is True


def test_known_confirmation_action_requires_approval():
    decision = PermissionEngine().assess_action("spending_money")
    assert decision.level == PermissionLevel.CONFIRM
    assert decision.requires_confirmation is True


def test_forbidden_action_is_blocked():
    assert PermissionEngine().assess_action("share_private_information").level == PermissionLevel.FORBIDDEN


def test_unknown_action_defaults_to_confirmation():
    assert PermissionEngine().assess_action("new_unknown_action").level == PermissionLevel.CONFIRM


def test_read_tool_is_safe():
    assert PermissionEngine().assess_tool("github", "read_file").level == PermissionLevel.SAFE


def test_mutating_tool_requires_confirmation():
    assert PermissionEngine().assess_tool("github", "update_file").level == PermissionLevel.CONFIRM


def test_shell_tool_is_high_risk():
    assert PermissionEngine().assess_tool("system", "run_command").level == PermissionLevel.HIGH_RISK


def test_unverified_read_is_elevated_to_confirmation():
    from core.trust_context import RequestSource, TrustContext

    context = TrustContext.unverified(source=RequestSource.LOCAL_VOICE)
    decision = PermissionEngine().assess_tool("github", "read_file", context=context)
    assert decision.level == PermissionLevel.CONFIRM


def test_unverified_mutation_is_elevated_to_high_risk():
    from core.trust_context import RequestSource, TrustContext

    context = TrustContext.unverified(source=RequestSource.LOCAL_VOICE)
    decision = PermissionEngine().assess_tool("github", "update_file", context=context)
    assert decision.level == PermissionLevel.HIGH_RISK


def test_locked_trusted_local_context_does_not_reduce_capability():
    from core.trust_context import TrustContext

    context = TrustContext.local_trusted(screen_locked=True)
    assert PermissionEngine().assess_tool("github", "read_file", context=context).level == PermissionLevel.SAFE
    assert PermissionEngine().assess_tool("system", "run_command", context=context).level == PermissionLevel.HIGH_RISK


def test_new_knowledge_root_requires_approval():
    decision = PermissionEngine().assess_tool("knowledge", "index_knowledge_path")
    assert decision.level == PermissionLevel.CONFIRM


def test_refreshing_approved_knowledge_roots_is_safe():
    decision = PermissionEngine().assess_tool("knowledge", "refresh_knowledge_index")
    assert decision.level == PermissionLevel.SAFE


def test_unverified_knowledge_refresh_is_elevated_to_confirmation():
    from core.trust_context import RequestSource, TrustContext

    context = TrustContext.unverified(source=RequestSource.LOCAL_VOICE)
    decision = PermissionEngine().assess_tool(
        "knowledge",
        "refresh_knowledge_index",
        context=context,
    )
    assert decision.level == PermissionLevel.CONFIRM
