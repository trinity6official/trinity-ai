from core.response_processing import ResponseProcessor


def test_format_normalization_lowercases_skill_and_removes_spacing():
    p = ResponseProcessor({})
    assert "github.read_file" in p.fix_skill_call_format("SKILL_CALL: GITHUB . read_file")


def test_repeated_failure_is_detected_and_reset():
    counts = {}
    p = ResponseProcessor(counts)
    p.record_skill_failure("SKILL_CALL: web.check_site")
    assert p.check_skill_call_loop("SKILL_CALL: web.check_site")[0] is False
    p.record_skill_failure("SKILL_CALL: web.check_site")
    assert p.check_skill_call_loop("SKILL_CALL: web.check_site")[0] is True
    p.reset_skill_failures()
    assert counts == {}


def test_clean_response_removes_raw_tool_artifacts():
    p = ResponseProcessor({})
    raw = "**Done**\nSKILL_CALL: github.read_file\nrepo: x\npath: y\n\n{'success': True, 'value': 1}"
    cleaned = p.clean_response(raw)
    assert cleaned == "Done"
