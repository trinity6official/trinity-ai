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

## Computer control

Read-only observations such as listing apps or reading approved workspace files can be safe. Desktop mutations—opening/activating apps, typing, clicking—and command execution require confirmation or high-risk approval.

## Self-modification

Trinity may identify a missing capability and draft code, but source-code creation/persistence is not an autonomous safe action. It must pass the same explicit approval path as other mutations. The exact generated unified diff is surfaced on the active interface and through `/pending` before approval, and approval applies the stored proposal rather than regenerating code.

## API exposure

The API binds to loopback by default. Binding to a LAN/VPN interface is refused unless both of these are configured:

- `TRINITY_APP_PIN_HASH`
- a strong `TRINITY_JWT_SECRET` of at least 32 characters

No-PIN development authentication is opt-in and intended only for local testing.

Remote phone commissioning is not complete until the transport itself is encrypted (for example, an approved encrypted VPN path or HTTPS/TLS) and the current PIN-hash scheme is migrated to a slow salted PIN/password KDF. Authentication tokens do not make plaintext LAN HTTP confidential.

## Memory and backups

Memory restore is confirmation-gated. Backup extraction rejects path traversal and links. Backups intentionally exclude `.env`, model weights and caches.

## Sensory privacy

Raw microphone chunks are temporary and removed after a voice turn. Screen captures are intended to be ephemeral and analyzed locally. Raw screenshot bytes are not written into the audit trail.

## Secrets

Do not commit `.env`, API tokens, JWT secrets, PINs or private keys to the repository or Memory Vault. Secrets should come from the local process environment/keychain-backed deployment configuration.
