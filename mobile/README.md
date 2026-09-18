# Trinity Mobile v0.1

Trinity Mobile is a thin authenticated Flutter client for the **single Trinity runtime**. It does not run a second AI brain and it does not store model-provider secrets.

## v0.1 features

- Runtime-configurable Trinity API address
- PIN login
- JWT stored with `flutter_secure_storage`
- Authenticated text chat through `/api/ask`
- Live `/api/status` connection indicator
- Optional hold-to-talk input
- Local/server TTS playback when available
- Logout (clears the JWT)
- Automatic redirect to login when the API returns `401`

## Architecture

```text
Trinity Mobile
   │
   ├── PIN ────────────────┐
   │                       ▼
   │              POST /api/auth/token
   │                       │
   │                       ▼
   │                  signed JWT
   │                       │
   └── Bearer JWT ─────────┤
                           ▼
                    Trinity API
                           │
                           ▼
                  same Trinity runtime
                    Memory / Model
                 Permissions / Agents
```

Authentication answers **which device/session may talk to Trinity**. Trinity's permission engine separately decides whether an action is safe, needs confirmation, or is forbidden.

## Same-S24 test

When Trinity API and the app both run on the S24, use:

```text
http://127.0.0.1:8000
```

The Android manifest permits cleartext HTTP only for local development/testing.

## Future M6 setup

When the M6 becomes the host, enter the Mac's trusted LAN/VPN URL on the login screen, for example:

```text
http://192.168.1.50:8000
```

For access outside a trusted LAN/VPN, use HTTPS/TLS. The mobile app should never expose Ollama, llama.cpp, or the Memory Vault directly.

## Build

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --release
```

A build-time default URL is optional:

```bash
flutter build apk --release \
  --dart-define=TRINITY_API_URL=http://127.0.0.1:8000
```

The address can still be changed at runtime from the login screen.
