# Mac Setup and Commissioning

This checklist is for commissioning Trinity on the target Apple Silicon Mac.

## 1. Runtime prerequisites

Run:

```bash
python -m core.macos_deployment preflight
python -m core.doctor
```

Required checks include macOS, Python 3.11+, Ollama and AppleScript. Local speech, microphone capture and screen capture are reported separately so voice/vision can be enabled only when their prerequisites are ready.

`core.doctor` also validates Ollama reachability, every configured model route, Memory Vault writability, API security posture and optional local voice readiness.

## 2. Install models

Install candidate local models in Ollama, then benchmark them instead of choosing routes from parameter count alone.

```bash
python -m core.model_benchmark --task fast --runs 3
python -m core.model_benchmark --task general --runs 3
python -m core.model_benchmark --task reasoning --runs 3
python -m core.model_benchmark --task coding --runs 3
```

Review latency, first-token time, throughput, memory pressure and response quality before editing `config/local_ai.yaml`.

## 3. Local permissions

When enabling features, macOS may require explicit permissions for microphone, accessibility/automation and screen recording. Grant only the permissions needed for enabled capabilities.

## 4. API/mobile

Keep the API on `127.0.0.1` unless remote phone access is required. For LAN/VPN binding, configure a PIN hash and strong JWT secret first.

## 5. Continuous runtime

Prepare the LaunchAgent:

```bash
python -m core.macos_deployment install
```

Review the generated plist before loading it. Trinity is configured to restart after failures, with local stdout/stderr logs under `logs/`.

## 6. Backup before tuning

```bash
python -m core.macos_deployment backup
```

Keep at least one verified Memory Vault backup before major model, memory or automation changes.

## 7. Hardware acceptance tests

Before calling the deployment production-ready, verify:

- cold boot and restart recovery;
- Ollama unavailable/restart behavior;
- model failover;
- memory migration/recall after restart;
- approval/denial flows;
- microphone STT and wake word in the real room;
- TTS voice quality and interruption behavior;
- screen recording/accessibility permission boundaries;
- vision model quality and privacy behavior;
- phone/API authentication over the intended LAN/VPN path;
- multi-hour then multi-day daemon soak behavior.
