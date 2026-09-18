# `config/` — Trinity Configuration

Configuration is local-first and intentionally separates model routing from wider Trinity runtime preferences.

## `local_ai.yaml`

Defines the local model provider, Ollama URL, ordered task candidates, and benchmark report location. Task routes are lists so Trinity can fail over to another installed local model.

Environment variables override YAML values when needed.

## `trinity_config.yaml`

Documents higher-level runtime intent: identity, timezone, hardware target, voice, vision, API, Presence, memory locations, and permission-engine defaults.

Do **not** store credentials, PINs, JWT secrets, private keys, or other secrets in committed YAML. Use environment variables or a local ignored `.env` mechanism instead.

Model names in the checked-in configuration are provisional defaults until benchmarked on the target Mac.

## `android_test.yaml`

Temporary Samsung/Termux profile using a local llama.cpp server. It is for pre-hardware testing only and does not replace the Mac/Ollama profile.
