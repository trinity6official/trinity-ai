# `voice/` — Local Voice Runtime

The voice subsystem is designed for local hardware operation:

```text
Microphone → Capture → Local STT → Trinity → Local TTS → Speaker
```

- `capture.py` — pluggable local audio capture.
- `local.py` — local speech provider abstractions/adapters.
- `runtime.py` — continuous microphone/listening runtime and resilience.
- `session.py` — wake-word/session/turn handling and interruption.
- `speak.py` — Trinity-facing speech compatibility layer.
- `language.py` — language detection/handling.

Raw captured audio should remain ephemeral and be deleted after use unless explicit persistence is requested.

The framework is production-oriented, but final microphone selection, Whisper model size, TTS engine, acoustic barge-in sensitivity, and language tuning must be benchmarked on the target M5 Pro Mac.
