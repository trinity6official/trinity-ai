from types import SimpleNamespace

from core.api_runtime import LocalAPIServer, validate_api_exposure
from core.api_security import hash_pin


def test_loopback_api_can_start_without_remote_credentials():
    assert validate_api_exposure(
        "127.0.0.1", pin_hash="", jwt_secret="change-me-please-use-a-real-secret"
    )[0]


def test_network_api_requires_encrypted_transport_and_strong_credentials(tmp_path):
    pin_hash = hash_pin("2468", salt=b"x" * 16)
    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash="", jwt_secret="x" * 40,
        remote_transport="vpn", cors_origins=(),
    )
    assert ok is False and "PBKDF2" in reason

    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash=pin_hash, jwt_secret="short",
        remote_transport="vpn", cors_origins=(),
    )
    assert ok is False and "JWT" in reason

    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash=pin_hash, jwt_secret="x" * 40,
        remote_transport="", cors_origins=(),
    )
    assert ok is False and "REMOTE_TRANSPORT" in reason

    ok, _ = validate_api_exposure(
        "100.64.0.10", pin_hash=pin_hash, jwt_secret="x" * 40,
        remote_transport="vpn", cors_origins=(),
    )
    assert ok is True

    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("cert")
    key.write_text("key")
    ok, _ = validate_api_exposure(
        "0.0.0.0", pin_hash=pin_hash, jwt_secret="x" * 40,
        remote_transport="https", tls_cert=str(cert), tls_key=str(key), cors_origins=(),
    )
    assert ok is True


def test_server_security_check_uses_environment(monkeypatch):
    monkeypatch.setenv("TRINITY_API_HOST", "0.0.0.0")
    monkeypatch.delenv("TRINITY_APP_PIN_HASH", raising=False)
    monkeypatch.setenv("TRINITY_API_REMOTE_TRANSPORT", "vpn")
    monkeypatch.setenv("TRINITY_API_CORS", "")
    server = LocalAPIServer(SimpleNamespace())
    assert server.security_check()[0] is False


def test_server_accepts_explicit_vpn_mode_with_strong_credentials(monkeypatch):
    monkeypatch.setenv("TRINITY_API_HOST", "100.64.0.10")
    monkeypatch.setenv("TRINITY_APP_PIN_HASH", hash_pin("2468", salt=b"z" * 16))
    monkeypatch.setenv("TRINITY_JWT_SECRET", "s" * 40)
    monkeypatch.setenv("TRINITY_API_REMOTE_TRANSPORT", "vpn")
    monkeypatch.setenv("TRINITY_API_CORS", "")
    server = LocalAPIServer(SimpleNamespace())
    assert server.security_check() == (True, "authenticated-vpn")
