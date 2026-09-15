import hashlib

from core.api_security import (
    DEFAULT_JWT_SECRET,
    strong_jwt_secret,
    validate_api_exposure,
    verify_pin,
)


def test_missing_pin_is_denied_by_default():
    assert verify_pin("anything", "") is False
    assert verify_pin("anything", "", dev_auth=True) is True


def test_pin_hash_uses_constant_time_digest_comparison_contract():
    digest = hashlib.sha256(b"2468").hexdigest()
    assert verify_pin("2468", digest) is True
    assert verify_pin("0000", digest) is False


def test_jwt_secret_must_be_changed_and_long_enough():
    assert strong_jwt_secret(DEFAULT_JWT_SECRET) is False
    assert strong_jwt_secret("short") is False
    assert strong_jwt_secret("x" * 32) is True


def test_remote_exposure_requires_pin_and_strong_secret():
    assert validate_api_exposure("127.0.0.1", pin_hash="", jwt_secret=DEFAULT_JWT_SECRET)[0] is True
    assert validate_api_exposure("0.0.0.0", pin_hash="", jwt_secret="x" * 32)[0] is False
    assert validate_api_exposure("0.0.0.0", pin_hash="hash", jwt_secret=DEFAULT_JWT_SECRET)[0] is False
    assert validate_api_exposure("0.0.0.0", pin_hash="hash", jwt_secret="x" * 32)[0] is True
