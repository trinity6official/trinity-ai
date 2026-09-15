"""Dependency-light security policy for Trinity's local HTTP API."""
from __future__ import annotations

import hashlib
import hmac


DEFAULT_JWT_SECRET = "change-me-please-use-a-real-secret"
_LOOPBACKS = {"127.0.0.1", "localhost", "::1"}


def flag_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_loopback(host: str) -> bool:
    return host.strip().lower() in _LOOPBACKS


def strong_jwt_secret(secret: str) -> bool:
    return bool(secret) and secret != DEFAULT_JWT_SECRET and len(secret) >= 32


def verify_pin(pin: str, pin_hash: str, *, dev_auth: bool = False) -> bool:
    """Verify a PIN without allowing implicit no-PIN authentication.

    ``dev_auth`` is intentionally explicit. It exists only for loopback/local
    development and must never be treated as production authentication.
    """
    if not pin_hash:
        return bool(dev_auth)
    candidate = hashlib.sha256(pin.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, pin_hash.strip().lower())


def validate_api_exposure(host: str, *, pin_hash: str, jwt_secret: str) -> tuple[bool, str]:
    """Refuse network exposure unless authentication is explicitly configured."""
    if is_loopback(host):
        return True, "loopback-only"
    if not pin_hash:
        return False, "TRINITY_APP_PIN_HASH is required for LAN/remote API exposure"
    if not strong_jwt_secret(jwt_secret):
        return False, "A strong TRINITY_JWT_SECRET (32+ characters) is required for LAN/remote API exposure"
    return True, "authenticated"
