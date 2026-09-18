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

When the M6 becomes the host, enter the Mac's HTTPS endpoint on the login screen, for example:

```text
https://trinity.example:8000
```

For an independently secured VPN tunnel, a build may explicitly trust HTTP inside that encrypted tunnel; the server must bind to the tunnel interface itself, not a wildcard LAN address.

Remote Trinity URLs use HTTPS by default. Same-device loopback HTTP is allowed for Android/Termux testing. If the Mac API is reachable only through an independently encrypted VPN tunnel, build the app with `--dart-define=TRINITY_ALLOW_VPN_HTTP=true`; never use that override for ordinary LAN HTTP. The mobile app should never expose Ollama, llama.cpp, or the Memory Vault directly.

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
