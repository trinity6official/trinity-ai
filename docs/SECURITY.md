# Trinity AI Security Model

## Trust boundaries

Trinity treats local reasoning, durable memory, external actions and computer control as separate trust boundaries. A model response is never permission by itself.

## Permission levels

- **Safe:** read-only/local analysis operations that may run autonomously.
- **Confirm:** mutating or external operations that require explicit approval.
- **High risk:** shell/production/security-sensitive actions that require explicit approval and extra scrutiny.
- **Forbidden:** actions Trinity must not execute.

Unknown tools default to confirmation.

## Action audit

Meaningful actions are recorded through a shared local audit stream using lifecycle events such as requested, approved/denied, started and completed/failed. Secret-bearing argument names are redacted before they reach audit records.

## Approval provenance

Approval authority is owned by Trinity's governed execution boundaries, not by request payloads.

- A caller-provided `approved=True` value is not proof of authorization for Skill or Agent execution.
- MCP rejects caller-forged pre-approved requests.
- Confirm-level requests are stored as immutable pending actions by the execution owner that created them.
- Only the execution owner's approval transition may resume that stored action.
- Approval/rejection continues the original `action_id`, so the audit trail represents one logical action rather than a second re-created request.
- Unverified request sources cannot consume owner approval authority.
- When more than one approval is pending, Trinity requires an explicit approval ID.

Lower-level capabilities may still receive an internal approved signal after the governing execution boundary has authorized the action. That signal is execution state, not caller authority.

## Computer control

Read-only observations such as listing apps or reading approved workspace files can be safe. Desktop mutations—opening/activating apps, typing, clicking—and command execution require confirmation or high-risk approval.

## Self-modification

Trinity may identify a missing capability and draft code, but source-code creation/persistence is not an autonomous safe action. It must pass the same explicit approval path as other mutations. The exact generated unified diff is surfaced on the active interface and through `/pending` before approval, and approval applies the stored proposal rather than regenerating code.

## API exposure

The API binds to loopback by default. Loopback HTTP is permitted for same-device development because traffic never leaves the host. Non-loopback exposure is refused unless **all** of the applicable controls are configured:

- `TRINITY_APP_PIN_HASH` uses Trinity's salted PBKDF2-HMAC-SHA256 verifier (`scripts/generate_app_pin_hash.py`). The legacy unsalted SHA-256 verifier is accepted only for local migration and is rejected for remote exposure.
- `TRINITY_JWT_SECRET` is changed from the default and is at least 32 characters.
- `TRINITY_API_REMOTE_TRANSPORT` is explicitly `https` or `vpn`.
- `https` mode requires `TRINITY_API_TLS_CERT` and `TRINITY_API_TLS_KEY` pointing to existing certificate/key files.
- `vpn` mode must bind to the **specific encrypted-tunnel interface/IP**, not `0.0.0.0` or another wildcard address. The flag is an operator assertion that the tunnel is actually encrypted.
- `TRINITY_API_CORS` must not contain `*` for non-loopback exposure. Native mobile clients do not need browser CORS origins, so an empty value is acceptable when there is no browser UI.

Generate a new PIN verifier with:

```bash
python scripts/generate_app_pin_hash.py
```

JWT access tokens carry issuer, audience and unique token identifiers and default to an 8-hour TTL, bounded to a maximum of 24 hours. Authentication is protected by HTTP rate limiting plus a longer-window failed-login lockout. Error messages intentionally avoid exposing token-decoding details.

The Android client rejects remote plaintext HTTP by default. Same-device loopback HTTP remains allowed. An operator using an independently secured VPN tunnel may explicitly build the app with `TRINITY_ALLOW_VPN_HTTP=true`; this should never be used for ordinary LAN HTTP.

No-PIN development authentication remains opt-in and is intended only for loopback testing. Do not expose Ollama, llama.cpp, Memory Vault files, or Trinity's Presence interface directly to the public Internet.

## Memory and backups

Memory restore is confirmation-gated. Backup extraction rejects path traversal and links. Backups intentionally exclude `.env`, model weights and caches.

## Sensory privacy

Raw microphone chunks are temporary and removed after a voice turn. Screen captures are intended to be ephemeral and analyzed locally. Raw screenshot bytes are not written into the audit trail.

## Secrets

Do not commit `.env`, API tokens, JWT secrets, PINs or private keys to the repository or Memory Vault. Secrets should come from the local process environment/keychain-backed deployment configuration.
