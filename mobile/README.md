# Trinity Voice — Mobile App

Flutter-based voice interface for the Trinity AI assistant.
This README captures every architectural decision made during the initial build
so that when the **Mac Mini M5 arrives (mid-2026)** the migration path is clear.

---

## Table of Contents

1. [What this is](#1-what-this-is)
2. [Architecture — Current (Pre-M5)](#2-architecture--current-pre-m5)
3. [Architecture — Production (Post-M5)](#3-architecture--production-post-m5)
4. [Why Flutter was chosen](#4-why-flutter-was-chosen)
5. [Full pipeline diagram](#5-full-pipeline-diagram)
6. [File structure](#6-file-structure)
7. [Environment variables](#7-environment-variables)
8. [Security design](#8-security-design)
9. [Setup guide — right now (laptop)](#9-setup-guide--right-now-laptop)
10. [Migration guide — when M5 arrives](#10-migration-guide--when-m5-arrives)
11. [Backend API reference](#11-backend-api-reference)
12. [Flutter dependencies explained](#12-flutter-dependencies-explained)
13. [Known limitations (pre-M5)](#13-known-limitations-pre-m5)
14. [Future features to build](#14-future-features-to-build)

---

## 1. What this is

Trinity is David's personal AI assistant. It lives in a GitHub repository,
runs via GitHub Actions on a schedule, operates as a Telegram bot, and now
has a voice interface through this mobile app.

The voice pipeline:
```
David speaks → phone transcribes → Trinity thinks → phone speaks back
```

The mobile app is a thin client. All AI reasoning stays server-side.
No API keys ever touch the phone.

---

## 2. Architecture — Current (Pre-M5)

**Status: Active. Use this until the M5 arrives.**

Because the Mac Mini M5 (the dedicated always-on server) is not released yet,
the backend runs on David's **development laptop**, and the mobile app uses
**Android's built-in on-device speech recognition** instead of uploading audio
to a server.

```
┌─────────────────────────────────────────────────────────────────┐
│  PRE-M5 ARCHITECTURE  (mid-2025 → mid-2026)                     │
│                                                                   │
│  ┌──────────────────────┐          ┌────────────────────────┐   │
│  │   Flutter App        │          │   Laptop (backend)     │   │
│  │   (Android phone)    │          │   python core/api.py   │   │
│  │                      │          │                        │   │
│  │  1. Hold mic button  │          │  POST /api/ask         │   │
│  │  2. Android STT      │  HTTPS   │  → Trinity brain       │   │
│  │     transcribes      │─────────►│    (Anthropic Claude)  │   │
│  │     on-device        │          │    + LLM failover      │   │
│  │  3. Send transcript  │          │  → gTTS (free TTS)     │   │
│  │  4. Receive text     │◄─────────│  → Return text + MP3   │   │
│  │     + MP3 audio      │          │                        │   │
│  │  5. Play response    │          └────────────────────────┘   │
│  └──────────────────────┘                                        │
│                                                                   │
│  STT:  Android on-device (Google speech, no API key)             │
│  TTS:  gTTS (open-source, free, no API key)                      │
│  LLM:  Anthropic Claude Haiku → Gemini fallback                  │
│  Auth: JWT HS256 (PIN → 24h token)                               │
│  Network: same Wi-Fi (laptop IP: 192.168.x.x:8000)               │
└─────────────────────────────────────────────────────────────────┘
```

**What you do NOT need right now:**
- Google Cloud Speech API key
- Google Cloud TTS API key
- Any cloud server
- Any paid service beyond your existing Anthropic key

---

## 3. Architecture — Production (Post-M5)

**Status: Planned for mid-2026 when Mac Mini M5 is available.**

The Mac Mini M5 runs 24/7 as a dedicated server. The mobile app switches
from on-device STT to server-side Google STT (higher accuracy, supports
Tamil script audio, handles accents better). Neural2 TTS replaces gTTS for
a natural voice.

```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION ARCHITECTURE  (mid-2026 onwards)                     │
│                                                                   │
│  ┌──────────────────────┐          ┌────────────────────────┐   │
│  │   Flutter App        │          │  Mac Mini M5 (server)  │   │
│  │   (Android + iOS)    │          │  python core/          │   │
│  │                      │          │    run_with_api.py     │   │
│  │  1. Hold mic button  │          │                        │   │
│  │  2. Record OGG/Opus  │  HTTPS   │  POST /api/voice       │   │
│  │     16kHz mono       │─────────►│  → Google Cloud STT    │   │
│  │  3. Upload audio     │          │    audio → transcript  │   │
│  │  4. Receive text     │◄─────────│  → Trinity brain       │   │
│  │     + MP3 audio      │          │    (Claude + failover) │   │
│  │  5. Play response    │          │  → Google Neural2 TTS  │   │
│  └──────────────────────┘          │    text → MP3 bytes    │   │
│                                    │  → Return text + MP3   │   │
│                                    │                        │   │
│                                    │  Also runs:            │   │
│                                    │  • Telegram bot        │   │
│                                    │  • GitHub sync         │   │
│                                    │  • Proactive checks    │   │
│                                    └────────────────────────┘   │
│                                                                   │
│  STT:  Google Cloud Speech v1 (en-US + ta-IN, Neural model)      │
│  TTS:  Google Cloud Neural2 TTS (en-US-Neural2-F / ta-IN-Std-A)  │
│  LLM:  Anthropic Claude Haiku → Gemini → Local Ollama            │
│  Auth: JWT HS256 (PIN → 24h token, configurable TTL)             │
│  Network: Public HTTPS via your domain / Cloudflare Tunnel        │
│  Deployment: python core/run_with_api.py (one command)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Why Flutter was chosen

Four options were evaluated before deciding.

### Option A — Native Android (Kotlin)
- Best raw performance
- Direct access to Android audio APIs
- **Rejected:** Android-only. iOS excluded forever. Two codebases if iOS wanted later.

### Option B — React Native
- Cross-platform (Android + iOS)
- Large ecosystem
- **Rejected:** JavaScript bridge between JS and native adds 30-60 ms on every
  audio frame. Voice assistants feel laggy. Audio plugin quality in RN ecosystem
  is inconsistent.

### Option C — Progressive Web App (PWA)
- No app installation needed
- Works in browser
- **Rejected:** Web Speech API is broken on iOS Safari. No background operation.
  Cannot stream raw audio to a custom backend. Wrong tool for a production voice
  product.

### Option D — Flutter ✓ CHOSEN
- Compiles to native ARM code (no JS bridge, no interpreter)
- One codebase runs on Android and iOS
- `speech_to_text` plugin uses native OS speech APIs
- `just_audio` is the best-maintained audio playback solution in mobile Flutter
- Can build an APK directly — no Play Store account needed for personal use
- Dart is easy to read and maintain

---

## 5. Full pipeline diagram

### Pre-M5 (current):
```
David says: "What's our GitHub status?"
        │
        ▼
[Android STT]  ← built into every Android phone, no key needed
        │
        │  transcript: "What's our GitHub status?"
        ▼
[POST /api/ask]  ← HTTP to laptop on same Wi-Fi
        │
        ▼
[JWT auth check]  ← server rejects if token expired
        │
[Rate limiter]  ← 30 req/min max
        │
        ▼
[Trinity brain — core/trinity.py]
        │
        ├── _invoke_with_failover()
        │       ├── Try: Anthropic Claude Haiku
        │       ├── If 529/overload → Try: Google Gemini Flash
        │       └── If all cloud down → Try: Local Ollama
        │
        │  response: "GitHub is healthy. Last commit was 2 hours ago..."
        ▼
[gTTS]  ← converts response text to MP3, free, no key
        │
        │  { text_response: "...", audio_base64: "..." }
        ▼
[Flutter app]
        │
        ├── Displays text bubble in conversation
        └── Plays MP3 audio via just_audio
```

### Post-M5 (future):
```
David says: "என்ன status?"  ← Tamil
        │
        ▼
[Flutter record pkg]  ← records OGG/Opus, 16kHz mono, 32kbps
        │
        │  audio bytes
        ▼
[POST /api/voice]  ← HTTPS to M5 via your domain
        │
[JWT auth + rate limit]
        │
        ▼
[Google Cloud STT]  ← ta-IN locale, neural model, auto-detects Tamil
        │
        │  transcript: "என்ன status?"
        ▼
[Trinity brain]  ← same LLM failover chain
        │
        │  response: "GitHub நல்ல நிலையில் உள்ளது..."  ← Tamil
        ▼
[Google Neural2 TTS]  ← ta-IN-Standard-A voice
        │   gTTS fallback if Google TTS fails
        ▼
[Flutter app plays MP3]
```

---

## 6. File structure

```
mobile/
├── README.md                          ← you are here
├── pubspec.yaml                       ← Flutter dependencies
├── android/
│   └── app/src/main/
│       └── AndroidManifest.xml        ← RECORD_AUDIO + INTERNET permissions
└── lib/
    ├── main.dart                      ← app entry point, auth gate, routing
    ├── config.dart                    ← TRINITY_API_URL and timeouts
    ├── screens/
    │   ├── login_screen.dart          ← PIN entry → JWT exchange
    │   └── voice_screen.dart          ← hold-to-talk UI, conversation bubbles
    └── services/
        ├── api_service.dart           ← HTTP client, JWT storage, error handling
        └── voice_service.dart         ← STT, audio playback, TTS fallback

Backend (in trinity-ai repo root):
core/
├── api.py                             ← FastAPI voice server
└── run_with_api.py                    ← starts Trinity + API together (M5 mode)
```

---

## 7. Environment variables

### Required on the backend server (laptop now, M5 later)

| Variable | What it is | How to get it |
|---|---|---|
| `TRINITY_JWT_SECRET` | Signs and verifies JWT tokens | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `TRINITY_APP_PIN_HASH` | SHA-256 of your PIN | `echo -n "YOUR_PIN" \| sha256sum` |
| `ANTHROPIC_API_KEY` | Claude AI (already have this) | https://console.anthropic.com |
| `GOOGLE_API_KEY` | Gemini fallback LLM (already have this) | https://aistudio.google.com |

### Required on backend — M5 only (not needed now)

| Variable | What it is | How to get it |
|---|---|---|
| `GOOGLE_CLOUD_API_KEY` | Google Cloud Speech + TTS | Enable APIs in Google Cloud Console, create API key |
| `TRINITY_API_PORT` | Port for FastAPI (default 8000) | Set to 443 behind nginx in production |
| `TRINITY_API_CORS` | Allowed origins (default `*`) | Set to `https://yourdomain.com` in production |
| `TRINITY_JWT_TTL_HOURS` | Token lifetime (default 24) | Increase for convenience, decrease for security |

### In the Flutter app (build-time, not runtime)

| Dart define | What it is | Default |
|---|---|---|
| `TRINITY_API_URL` | Backend server URL | `http://10.0.2.2:8000` (Android emulator) |

Set at build time:
```bash
flutter build apk --dart-define=TRINITY_API_URL=http://192.168.1.x:8000
```

---

## 8. Security design

### How auth works
```
1. User opens app → stored JWT found → go to voice screen
   User opens app → no stored JWT → show PIN screen

2. User enters PIN
   App: POST /api/auth/token  { "pin": "1234" }
   Server: SHA-256(pin) == TRINITY_APP_PIN_HASH ?
     YES → issue JWT (HS256, signed with TRINITY_JWT_SECRET, 24h TTL)
     NO  → 401 Unauthorized

3. JWT stored in flutter_secure_storage
   Android: EncryptedSharedPreferences (hardware-backed encryption)
   iOS: Keychain Services

4. Every request: Authorization: Bearer <token>
   Server verifies signature + expiry before processing
   On 401: app deletes token, shows PIN screen again
```

### What is never in the app
- `ANTHROPIC_API_KEY` — never leaves the server
- `GOOGLE_API_KEY` / `GOOGLE_CLOUD_API_KEY` — never leaves the server
- `TELEGRAM_BOT_TOKEN` — never leaves the server
- The raw PIN — only the SHA-256 hash is stored on the server

### Rate limits (server-side)
| Endpoint | Limit |
|---|---|
| `POST /api/auth/token` | 5 requests/minute |
| `POST /api/voice` | 20 requests/minute |
| `POST /api/ask` | 30 requests/minute |

---

## 9. Setup guide — right now (laptop)

### What you need
- Your existing laptop (Mac or Linux)
- An Android phone
- Both on the same Wi-Fi network
- Flutter SDK installed
- Your `ANTHROPIC_API_KEY` (already have it)

### Step 1 — Install Flutter

```bash
# macOS
brew install flutter

# Or download from https://docs.flutter.dev/get-started/install
flutter doctor        # fix any issues shown
flutter doctor --android-licenses   # accept Android licenses
```

### Step 2 — Install backend dependencies

```bash
cd /path/to/trinity-ai
pip install python-jose[cryptography] slowapi python-multipart
```

### Step 3 — Configure the server

```bash
# Generate a JWT secret (save this somewhere safe)
python -c "import secrets; print(secrets.token_hex(32))"

# Generate PIN hash (change 1234 to your actual PIN)
echo -n "1234" | sha256sum | awk '{print $1}'

# Set all environment variables
export TRINITY_JWT_SECRET="the_hex_string_from_step_above"
export TRINITY_APP_PIN_HASH="sha256_of_your_pin"
export ANTHROPIC_API_KEY="your_existing_anthropic_key"
export GOOGLE_API_KEY="your_existing_gemini_key"
```

### Step 4 — Start the server

```bash
python core/api.py
# Output: INFO: Uvicorn running on http://0.0.0.0:8000
```

Verify it works:
```bash
curl http://localhost:8000/api/status
# {"status":"ok","version":"1.0.0",...}
```

### Step 5 — Find your laptop's IP address

```bash
# macOS
ipconfig getifaddr en0      # Wi-Fi interface
# example output: 192.168.1.45

# Linux
hostname -I | awk '{print $1}'
```

Your phone will connect to this IP. Both must be on the same Wi-Fi.

### Step 6 — Build and install the Flutter app

```bash
cd mobile
flutter pub get

# Run directly on connected phone (USB debugging enabled)
flutter run --dart-define=TRINITY_API_URL=http://192.168.1.45:8000

# OR build an APK to install manually
flutter build apk --dart-define=TRINITY_API_URL=http://192.168.1.45:8000

# Install APK via ADB
adb install build/app/outputs/flutter-apk/app-release.apk
```

### Step 7 — Enable USB debugging on Android

Settings → About phone → tap "Build number" 7 times → Developer options →
Enable "USB debugging"

### Step 8 — Test it

1. Open Trinity app
2. Enter your PIN → Connect
3. Hold the mic button → speak
4. Release → see live transcript appear while you speak
5. "Thinking..." appears
6. Trinity's response plays as audio and appears as text

---

## 10. Migration guide — when M5 arrives

When the Mac Mini M5 is set up, follow these steps to upgrade to the full
production architecture. **The backend code is already written** — only the
mobile app needs changes.

### Backend changes (core/api.py) — already done, no changes needed
The server already supports:
- `POST /api/voice` — audio upload → Google Cloud STT → Trinity → Google TTS
- `POST /api/ask` — text only (what we use now)

### Step 1 — Enable Google Cloud APIs

1. Go to https://console.cloud.google.com
2. Create or select a project
3. Enable:
   - Cloud Speech-to-Text API
   - Cloud Text-to-Speech API
4. Create an API key (APIs & Services → Credentials → Create API Key)
5. Restrict the key to only Speech + TTS APIs

### Step 2 — Set environment variables on M5

```bash
export GOOGLE_CLOUD_API_KEY="your_new_cloud_key"
export TRINITY_JWT_SECRET="same_secret_as_before"
export TRINITY_APP_PIN_HASH="same_pin_hash_as_before"
export ANTHROPIC_API_KEY="your_anthropic_key"
export GOOGLE_API_KEY="your_gemini_key"
export TELEGRAM_BOT_TOKEN="your_telegram_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export GH_TOKEN="your_github_token"
export TRINITY_API_CORS="https://trinity.yourdomain.com"
```

### Step 3 — Run the unified server

```bash
# This command starts BOTH the Telegram bot AND the voice API together
python core/run_with_api.py
```

### Step 4 — Update pubspec.yaml

Add back the audio recording package:
```yaml
# Add this under dependencies:
record: ^5.1.2        # raw audio recording for server-side STT
```

Remove (no longer needed):
```yaml
# Remove:
speech_to_text: ^6.6.2
```

### Step 5 — Update voice_service.dart

Replace the `SpeechToText`-based implementation with raw audio recording.
The original implementation is in git history (commit message: "Add voice
pipeline: FastAPI backend + Flutter mobile app"). The key changes:

```dart
// BEFORE (on-device STT):
Future<void> startListening({required void Function(String) onPartial}) async {
  await _stt.listen(onResult: ..., listenMode: ListenMode.confirmation);
}
Future<String> stopListening() async {
  await _stt.stop();
  return _lastTranscript;
}

// AFTER (raw audio recording):
Future<void> startRecording() async {
  await _recorder.start(
    RecordConfig(encoder: AudioEncoder.opus, sampleRate: 16000, numChannels: 1),
    path: tempPath,
  );
}
Future<File?> stopRecording() async {
  final path = await _recorder.stop();
  return path != null ? File(path) : null;
}
```

### Step 6 — Update voice_screen.dart

Change the send call from text to audio:
```dart
// BEFORE:
final transcript = await _voice.stopListening();
await _sendText(transcript);         // POST /api/ask

// AFTER:
final file = await _voice.stopRecording();
await _sendAudio(file);              // POST /api/voice
```

### Step 7 — Update config.dart

```dart
// Change default URL to your M5's domain
static const String baseUrl = String.fromEnvironment(
  'TRINITY_API_URL',
  defaultValue: 'https://trinity.yourdomain.com',  // ← change this
);
```

### Step 8 — Rebuild APK

```bash
cd mobile
flutter build apk --dart-define=TRINITY_API_URL=https://trinity.yourdomain.com
```

### Exposing M5 to the internet (options)

**Option A — Cloudflare Tunnel (recommended, free)**
```bash
# Install cloudflared on M5
brew install cloudflare/cloudflare/cloudflared

# Create a tunnel (one-time setup)
cloudflared tunnel login
cloudflared tunnel create trinity
cloudflared tunnel route dns trinity trinity.yourdomain.com

# Run tunnel (add to startup)
cloudflared tunnel run trinity
```
This gives you a permanent HTTPS URL with no port forwarding and no open ports.

**Option B — ngrok (free tier, URL changes on restart)**
```bash
ngrok http 8000
# Gets you: https://abc123.ngrok.io
```
Good for testing. Not suitable for permanent use (URL changes on free plan).

**Option C — nginx + Let's Encrypt (self-hosted, full control)**
```nginx
server {
    listen 443 ssl;
    server_name trinity.yourdomain.com;
    ssl_certificate     /etc/letsencrypt/live/trinity.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trinity.yourdomain.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 11. Backend API reference

Base URL: `http://192.168.x.x:8000` (now) / `https://trinity.yourdomain.com` (M5)

### POST /api/auth/token
Exchange PIN for JWT. Rate limit: 5/min.

**Request:**
```json
{ "pin": "1234" }
```
**Response (200):**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 86400
}
```
**Response (401):** Wrong PIN.

---

### POST /api/ask
Send text, get Trinity's response + optional TTS audio. Rate limit: 30/min.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "text": "What is our GitHub status?",
  "language": "english",
  "tts": true
}
```
`language`: `"english"` or `"tamil"` (auto-detected if omitted)
`tts`: include MP3 audio in response (default true)

**Response (200):**
```json
{
  "text_input": "What is our GitHub status?",
  "text_response": "GitHub is healthy. Last commit was 3 hours ago...",
  "language": "english",
  "audio_base64": "//NExAAA..."
}
```
`audio_base64`: Base64-encoded MP3 file. Decode and play as audio.
Null if `tts: false` or TTS failed.

---

### POST /api/voice
Upload audio, get response. M5-era endpoint. Rate limit: 20/min.

**Headers:** `Authorization: Bearer <token>`

**Body:** `multipart/form-data`
- `audio`: audio file (OGG/Opus preferred, also WAV/WebM/MP3)
- `language`: `english` or `tamil` (optional form field)
- `tts`: `true` or `false` (optional, default true)

**Response:** same shape as `/api/ask`

---

### GET /api/status
Health check. No auth required.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "time": "2026-03-04T10:00:00+00:00",
  "google_stt_available": false,
  "google_tts_available": false
}
```

---

## 12. Flutter dependencies explained

| Package | Version | Why |
|---|---|---|
| `speech_to_text` | ^6.6.2 | On-device STT. Uses Android's built-in speech engine. No API key. Replaced by `record` when M5 arrives. |
| `just_audio` | ^0.9.38 | Plays MP3 audio returned from backend TTS. Best-maintained audio player in Flutter. |
| `flutter_tts` | ^4.0.2 | Device TTS fallback. Used when backend TTS fails or network is down. |
| `http` | ^1.2.1 | HTTP client for API calls. Lightweight and stable. |
| `flutter_secure_storage` | ^9.2.2 | Stores JWT token securely. Android: EncryptedSharedPreferences. iOS: Keychain. |
| `permission_handler` | ^11.3.1 | Requests microphone permission at runtime. |
| `path_provider` | ^2.1.3 | Gets temp directory path for saving MP3 files during playback. |

### Future additions (M5 era)
| Package | Version | Why |
|---|---|---|
| `record` | ^5.1.2 | Records OGG/Opus audio at 16kHz mono for upload to backend STT. Replaces `speech_to_text`. |

---

## 13. Known limitations (pre-M5)

| Limitation | Cause | Fix when M5 arrives |
|---|---|---|
| Both devices must be on same Wi-Fi | No public server yet | Cloudflare Tunnel or nginx on M5 |
| STT quality depends on phone model | Android on-device STT varies by manufacturer | Google Cloud STT (consistent quality, neural model) |
| Tamil speech not always recognised | On-device STT has limited Tamil models on most phones | Google Cloud STT with ta-IN locale is excellent for Tamil |
| TTS voice quality is robotic (gTTS) | gTTS uses basic synthesis | Google Neural2 TTS (natural-sounding) |
| Server stops when laptop sleeps | No always-on machine | M5 runs 24/7, never sleeps |
| No HTTPS (HTTP only on LAN) | Trusted local network only | nginx + Let's Encrypt or Cloudflare Tunnel on M5 |
| Manual server start each time | No daemon/service yet | systemd service on M5 auto-starts on boot |
| Conversation history resets on server restart | Trinity brain not persisted between API sessions | Resolved when M5 runs continuously |

---

## 14. Future features to build

These were discussed but not built yet. Review this list when M5 is set up.

### Near-term (M5 setup)
- [ ] Auto-start Trinity API as a macOS launchd service on boot
- [ ] Push notifications when Trinity proactively wants to tell David something
- [ ] Conversation history persisted per-device (not just in-memory)
- [ ] Dark/light theme toggle

### Medium-term
- [ ] Wake word detection ("Hey Trinity") — always-listening without holding button
- [ ] Streaming TTS — audio starts playing before full response is generated
- [ ] iOS build and TestFlight distribution
- [ ] Home screen widget showing Trinity's last proactive message

### Long-term
- [ ] Multi-language live switching (Tamil mid-sentence to English)
- [ ] Offline mode — local Ollama on M5 answers when internet is down
- [ ] Voice profile — Trinity recognises David's voice (rejects strangers)
- [ ] Smart home integration — Trinity controls Home Assistant via voice

---

## Notes written at build time (March 2026)

**Why gTTS instead of a better TTS now:**
gTTS produces MP3 directly, requires no API key, and is already in
`requirements.txt`. The audio quality is acceptable for functional testing.
The switch to Google Neural2 TTS is one environment variable away — no code
change needed, just set `GOOGLE_CLOUD_API_KEY` on the server.

**Why PIN instead of biometric auth:**
Biometric auth (fingerprint/face) requires platform-specific code and a
server-side session management system. PIN→JWT is secure enough for a
personal assistant and keeps the codebase simple. When the user base grows
beyond one person, upgrade to biometric + short-lived refresh tokens.

**Why on-device STT sends text (not audio) to the backend:**
Sending audio requires `multipart/form-data` upload, server-side decoding,
and a Google Cloud account. Sending a text transcript to `/api/ask` requires
none of that — it's a simple JSON POST. The voice quality difference is not
noticeable for a single-user personal assistant.

**LLM failover was implemented before this mobile work:**
If Anthropic's API is overloaded (HTTP 529), Trinity automatically switches
to Google Gemini, then to local Ollama if available. The mobile app benefits
from this automatically — it never sees the error.

**The M5 migration is one day of work, not a rewrite:**
The server code for `/api/voice` (audio upload + Google Cloud STT) is already
written in `core/api.py`. The Flutter migration is swapping `speech_to_text`
for `record` and changing one method call in `voice_screen.dart`. Everything
else stays the same.
