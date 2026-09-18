"""Dependency-light security policy for Trinity's local HTTP API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Iterable


DEFAULT_JWT_SECRET = "change-me-please-use-a-real-secret"
DEFAULT_PIN_ITERATIONS = 600_000
DEFAULT_JWT_TTL_MINUTES = 480
MAX_JWT_TTL_MINUTES = 1440
MIN_JWT_TTL_MINUTES = 5
MIN_PIN_ITERATIONS = 600_000
PIN_SCHEME = "pbkdf2_sha256"
_LOOPBACKS = {"127.0.0.1", "localhost", "::1"}
_WILDCARD_HOSTS = {"0.0.0.0", "::", "[::]"}
_REMOTE_TRANSPORTS = {"https", "vpn"}


def flag_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_loopback(host: str) -> bool:
    return host.strip().lower() in _LOOPBACKS


def strong_jwt_secret(secret: str) -> bool:
    return bool(secret) and secret != DEFAULT_JWT_SECRET and len(secret) >= 32


def bounded_jwt_ttl_minutes(value: str | int | None) -> int:
    try:
        parsed = int(value if value is not None else DEFAULT_JWT_TTL_MINUTES)
    except (TypeError, ValueError):
        parsed = DEFAULT_JWT_TTL_MINUTES
    return min(MAX_JWT_TTL_MINUTES, max(MIN_JWT_TTL_MINUTES, parsed))


def build_jwt_claims(
    subject: str,
    *,
    ttl_minutes: int = DEFAULT_JWT_TTL_MINUTES,
    issuer: str = "trinity-local",
    audience: str = "trinity-mobile",
    now: datetime | None = None,
    jti: str | None = None,
) -> dict[str, object]:
    issued_at = now or datetime.now(timezone.utc)
    ttl = bounded_jwt_ttl_minutes(ttl_minutes)
    return {
        "sub": subject,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": issued_at + timedelta(minutes=ttl),
        "iss": issuer,
        "aud": audience,
        "jti": jti or secrets.token_urlsafe(18),
    }


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_pin(
    pin: str,
    *,
    iterations: int = DEFAULT_PIN_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    """Return a versioned salted PBKDF2-HMAC-SHA256 PIN verifier."""
    if not pin:
        raise ValueError("PIN cannot be empty")
    if iterations < MIN_PIN_ITERATIONS:
        raise ValueError(f"PIN KDF iterations must be at least {MIN_PIN_ITERATIONS}")
    salt_bytes = salt or secrets.token_bytes(16)
    if len(salt_bytes) < 16:
        raise ValueError("PIN KDF salt must be at least 16 bytes")
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt_bytes,
        iterations,
        dklen=32,
    )
    return f"{PIN_SCHEME}${iterations}${_b64encode(salt_bytes)}${_b64encode(digest)}"


def _parse_strong_pin_hash(pin_hash: str) -> tuple[int, bytes, bytes] | None:
    try:
        scheme, iterations_raw, salt_raw, digest_raw = pin_hash.strip().split("$", 3)
        if scheme != PIN_SCHEME:
            return None
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        digest = _b64decode(digest_raw)
        if iterations < MIN_PIN_ITERATIONS or len(salt) < 16 or len(digest) != 32:
            return None
        return iterations, salt, digest
    except (ValueError, TypeError, binascii.Error):
        return None


def is_legacy_pin_hash(pin_hash: str) -> bool:
    """Return True for the retired unsalted SHA-256 verifier format."""
    value = str(pin_hash or "").strip().lower()
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def strong_pin_hash(pin_hash: str) -> bool:
    return _parse_strong_pin_hash(pin_hash) is not None


def verify_pin(pin: str, pin_hash: str, *, dev_auth: bool = False) -> bool:
    """Verify a PIN while retaining loopback-only legacy migration support.

    New configuration must use :func:`hash_pin`. Legacy unsalted SHA-256
    verifiers remain readable only so an existing local installation can log in
    long enough to migrate; remote exposure rejects them.
    """
    if not pin_hash:
        return bool(dev_auth)

    parsed = _parse_strong_pin_hash(pin_hash)
    if parsed is not None:
        iterations, salt, expected = parsed
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            pin.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected),
        )
        return hmac.compare_digest(candidate, expected)

    if is_legacy_pin_hash(pin_hash):
        candidate = hashlib.sha256(pin.encode("utf-8")).hexdigest()
        return hmac.compare_digest(candidate, pin_hash.strip().lower())
    return False


def _cors_is_remote_safe(origins: Iterable[str]) -> bool:
    normalized = {str(value).strip() for value in origins if str(value).strip()}
    return "*" not in normalized


def validate_api_exposure(
    host: str,
    *,
    pin_hash: str,
    jwt_secret: str,
    remote_transport: str = "",
    tls_cert: str = "",
    tls_key: str = "",
    cors_origins: Iterable[str] = ("*",),
) -> tuple[bool, str]:
    """Refuse non-loopback exposure without strong auth and encrypted transport."""
    if is_loopback(host):
        return True, "loopback-only"
    if not strong_pin_hash(pin_hash):
        return False, "A salted PBKDF2 TRINITY_APP_PIN_HASH is required for LAN/remote API exposure"
    if not strong_jwt_secret(jwt_secret):
        return False, "A strong TRINITY_JWT_SECRET (32+ characters) is required for LAN/remote API exposure"

    transport = str(remote_transport or "").strip().lower()
    if transport not in _REMOTE_TRANSPORTS:
        return False, "TRINITY_API_REMOTE_TRANSPORT must be explicitly set to 'https' or 'vpn' for LAN/remote exposure"
    if transport == "vpn" and host.strip().lower() in _WILDCARD_HOSTS:
        return False, "VPN mode must bind to the specific encrypted-tunnel interface, not a wildcard host"
    if transport == "https":
        if not tls_cert or not tls_key:
            return False, "HTTPS exposure requires TRINITY_API_TLS_CERT and TRINITY_API_TLS_KEY"
        if not Path(tls_cert).is_file() or not Path(tls_key).is_file():
            return False, "Configured TLS certificate/key files do not exist"
    if not _cors_is_remote_safe(cors_origins):
        return False, "TRINITY_API_CORS must not contain '*' for LAN/remote exposure"
    return True, f"authenticated-{transport}"


@dataclass(frozen=True)
class LoginGuardDecision:
    allowed: bool
    retry_after_seconds: int = 0


class LoginAttemptGuard:
    """In-memory brute-force guard layered on top of HTTP rate limiting."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 10 * 60,
        lockout_seconds: int = 15 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max(1, int(max_failures))
        self.window_seconds = max(1, int(window_seconds))
        self.lockout_seconds = max(1, int(lockout_seconds))
        self.clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = Lock()

    def check(self, client_id: str) -> LoginGuardDecision:
        now = self.clock()
        key = client_id or "unknown"
        with self._lock:
            locked_until = self._locked_until.get(key, 0.0)
            if locked_until > now:
                return LoginGuardDecision(False, max(1, int(locked_until - now)))
            self._locked_until.pop(key, None)
            self._prune_locked(key, now)
            return LoginGuardDecision(True, 0)

    def record_failure(self, client_id: str) -> LoginGuardDecision:
        now = self.clock()
        key = client_id or "unknown"
        with self._lock:
            failures = self._failures[key]
            self._prune(failures, now)
            failures.append(now)
            if len(failures) >= self.max_failures:
                self._locked_until[key] = now + self.lockout_seconds
                failures.clear()
                return LoginGuardDecision(False, self.lockout_seconds)
            return LoginGuardDecision(True, 0)

    def record_success(self, client_id: str) -> None:
        key = client_id or "unknown"
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def _prune_locked(self, key: str, now: float) -> None:
        failures = self._failures.get(key)
        if failures is None:
            return
        self._prune(failures, now)
        if not failures:
            self._failures.pop(key, None)

    def _prune(self, failures: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while failures and failures[0] < cutoff:
            failures.popleft()
