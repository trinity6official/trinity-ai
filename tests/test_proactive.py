from core.proactive import ProactiveEngine


def test_silent_token_produces_silent_decision():
    assert ProactiveEngine().parse("TRINITY_SILENT").silent is True


def test_empty_response_is_silent():
    assert ProactiveEngine().parse("  ").silent is True


def test_message_is_preserved():
    decision = ProactiveEngine().parse("Database scanner failed twice today.")
    assert decision.silent is False
    assert decision.message == "Database scanner failed twice today."


def test_skill_request_is_extracted_and_hidden_from_message():
    decision = ProactiveEngine().parse(
        "I found a capability gap.\nTRINITY_SKILL_NEED: email_agent | Need inbox triage"
    )
    assert decision.message == "I found a capability gap."
    assert decision.skill_requests[0].name == "email_agent"
    assert decision.skill_requests[0].reason == "Need inbox triage"


def test_prompt_includes_awareness_context():
    prompt = ProactiveEngine().build_prompt(
        now="Monday 10:00",
        consciousness_context="state",
        company_context="company",
        awareness_context="last error: timeout",
    )
    assert "last error: timeout" in prompt
    assert "TRINITY_SILENT" in prompt


def test_prompt_is_domain_neutral():
    prompt = ProactiveEngine().build_prompt(
        now="Monday 10:00",
        consciousness_context="state",
        company_context="personal and work context",
    )
    assert "personal AI company manager" not in prompt
    assert "Relevant personal/work context" in prompt
