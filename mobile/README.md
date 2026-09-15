# `mobile/` — Trinity Mobile Client

Trinity Mobile is a thin authenticated client for the **single local Trinity runtime on the Mac**. It is not a second AI brain and should never contain model-provider secrets.

## Architecture

```text
Android / iOS
   │
   │ authenticated LAN/VPN/API
   ▼
Trinity API on Mac
   │
   ├── Conversation + Memory
   ├── Local Model Router
   ├── Permission + Audit
   ├── Agents / Skills
   ├── Local Voice
   └── Local Vision
```

The phone can capture text/voice and display/play responses, but reasoning, durable memory, permissions, and side-effect execution remain on the Mac.

## Configure the API URL

Development/LAN example:

```bash
flutter run --dart-define=TRINITY_API_URL=http://192.168.x.x:8000
```

Production/VPN/TLS example:

```bash
flutter run --dart-define=TRINITY_API_URL=https://trinity.example.com
```

GitHub's APK workflow requires `TRINITY_API_URL` (or a manual override) and will not silently build against a cloud placeholder.

## Security

- Keep server-side secrets on the Mac.
- Store only short-lived auth material in mobile secure storage.
- Prefer trusted LAN/VPN connectivity.
- Use TLS when crossing untrusted networks.
- Never expose Ollama or the Memory Vault directly.
- Do not disable API security just to make mobile networking easier.

Telegram is a separate optional channel and is not required by the mobile client.
