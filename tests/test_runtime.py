from core.runtime import RuntimeMode, detect_runtime


def test_local_daemon_is_default():
    assert detect_runtime({}) == RuntimeMode.LOCAL_DAEMON


def test_github_actions_is_ci():
    assert detect_runtime({"GITHUB_ACTIONS": "true"}) == RuntimeMode.CI


def test_generic_ci_is_ci():
    assert detect_runtime({"CI": "1"}) == RuntimeMode.CI


def test_local_oneshot_can_be_requested():
    assert detect_runtime({"TRINITY_ONESHOT": "true"}) == RuntimeMode.LOCAL_ONESHOT
