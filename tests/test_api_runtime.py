from types import SimpleNamespace

from core.api_runtime import LocalAPIServer, validate_api_exposure


def test_loopback_api_can_start_without_remote_credentials():
    assert validate_api_exposure("127.0.0.1", pin_hash="", jwt_secret="change-me-please-use-a-real-secret")[0]


def test_network_api_requires_pin_and_strong_secret():
    ok, reason = validate_api_exposure("0.0.0.0", pin_hash="", jwt_secret="x" * 40)
    assert ok is False and "PIN" in reason
    ok, reason = validate_api_exposure("0.0.0.0", pin_hash="hash", jwt_secret="short")
    assert ok is False and "JWT" in reason
    ok, _ = validate_api_exposure("0.0.0.0", pin_hash="hash", jwt_secret="x" * 40)
    assert ok is True


def test_server_security_check_uses_environment(monkeypatch):
    monkeypatch.setenv("TRINITY_API_HOST", "0.0.0.0")
    monkeypatch.delenv("TRINITY_APP_PIN_HASH", raising=False)
    server = LocalAPIServer(SimpleNamespace())
    assert server.security_check()[0] is False
