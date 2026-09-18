import hashlib

from core.api_security import (
    DEFAULT_JWT_SECRET,
    LoginAttemptGuard,
    hash_pin,
    is_legacy_pin_hash,
    strong_jwt_secret,
    strong_pin_hash,
    validate_api_exposure,
    verify_pin,
)


def test_missing_pin_is_denied_by_default():
    assert verify_pin("anything", "") is False
    assert verify_pin("anything", "", dev_auth=True) is True


def test_new_pin_hash_is_salted_slow_and_verifiable():
    first = hash_pin("2468", salt=b"a" * 16)
    second = hash_pin("2468", salt=b"b" * 16)
    assert first.startswith("pbkdf2_sha256$600000$")
    assert first != second
    assert strong_pin_hash(first) is True
    assert verify_pin("2468", first) is True
    assert verify_pin("0000", first) is False


def test_legacy_sha256_pin_hash_remains_local_migration_compatible():
    digest = hashlib.sha256(b"2468").hexdigest()
    assert is_legacy_pin_hash(digest) is True
    assert strong_pin_hash(digest) is False
    assert verify_pin("2468", digest) is True
    assert verify_pin("0000", digest) is False


def test_jwt_secret_must_be_changed_and_long_enough():
    assert strong_jwt_secret(DEFAULT_JWT_SECRET) is False
    assert strong_jwt_secret("short") is False
    assert strong_jwt_secret("x" * 32) is True


def test_remote_exposure_requires_strong_pin_secret_transport_and_cors(tmp_path):
    pin_hash = hash_pin("2468", salt=b"s" * 16)
    secret = "x" * 40
    assert validate_api_exposure("127.0.0.1", pin_hash="", jwt_secret=DEFAULT_JWT_SECRET)[0] is True

    legacy = hashlib.sha256(b"2468").hexdigest()
    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash=legacy, jwt_secret=secret,
        remote_transport="vpn", cors_origins=(),
    )
    assert ok is False and "PBKDF2" in reason

    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash=pin_hash, jwt_secret=secret,
        remote_transport="", cors_origins=(),
    )
    assert ok is False and "REMOTE_TRANSPORT" in reason

    ok, reason = validate_api_exposure(
        "100.64.0.10", pin_hash=pin_hash, jwt_secret=secret,
        remote_transport="vpn", cors_origins=("*",),
    )
    assert ok is False and "CORS" in reason

    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash=pin_hash, jwt_secret=secret,
        remote_transport="vpn", cors_origins=(),
    )
    assert ok is False and "specific encrypted-tunnel interface" in reason

    ok, reason = validate_api_exposure(
        "100.64.0.10", pin_hash=pin_hash, jwt_secret=secret,
        remote_transport="vpn", cors_origins=(),
    )
    assert ok is True and reason == "authenticated-vpn"

    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("cert")
    key.write_text("key")
    ok, reason = validate_api_exposure(
        "0.0.0.0", pin_hash=pin_hash, jwt_secret=secret,
        remote_transport="https", tls_cert=str(cert), tls_key=str(key),
        cors_origins=("https://app.trinity.local",),
    )
    assert ok is True and reason == "authenticated-https"


def test_login_attempt_guard_locks_and_recovers():
    now = [100.0]
    guard = LoginAttemptGuard(
        max_failures=3,
        window_seconds=60,
        lockout_seconds=120,
        clock=lambda: now[0],
    )
    assert guard.check("phone").allowed is True
    assert guard.record_failure("phone").allowed is True
    assert guard.record_failure("phone").allowed is True
    locked = guard.record_failure("phone")
    assert locked.allowed is False
    assert locked.retry_after_seconds == 120
    assert guard.check("phone").allowed is False

    now[0] += 121
    assert guard.check("phone").allowed is True
    guard.record_failure("phone")
    guard.record_success("phone")
    assert guard.check("phone").allowed is True
