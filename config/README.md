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

## `mcp_servers.yaml`

Defines local MCP stdio commands, arguments, request timeouts, and the explicit environment-variable allowlist each child process may inherit. The checked-in file contains no enabled servers. Secrets remain in the host environment and are passed only when named in `env_passthrough`. PR #14 owns transport/lifecycle/discovery; PR #15 indexes cached discoveries in the Capability Registry; PR #16 permits execution only when a server is explicitly enabled for execution and the exact tool is allowlisted. `trust`, `execution_enabled`, `allowed_tools`, and `result_limit_bytes` are deny-by-default governance controls.
