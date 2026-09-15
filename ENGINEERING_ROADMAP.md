# Trinity AI Engineering Roadmap

## Completed in the local architecture upgrade

- Provider-neutral Local Model Router with Ollama adapter and local-only failover.
- YAML + environment model routing configuration.
- SQLite + Markdown Memory Vault and legacy migration.
- Conversation memory extraction/deduplication/recall.
- Brain/orchestrator decomposition; `Trinity` is now primarily the composition root.
- Optional Telegram channel isolation.
- Central permission engine and shared action audit.
- Unified agent registry and agent capability contracts.
- Event bus, awareness, proactive scheduling and duplicate suppression.
- Local voice abstraction, microphone runtime and wake-word/session controller.
- Local vision/screen-awareness framework with ephemeral image handling.
- Permission-gated computer control and generic resumable approval queue.
- Presence state engine and localhost visualizer.
- Secure local API/mobile bridge.
- macOS launchd/preflight/logging/backup/restore tooling.
- GitHub Actions repositioned to CI/build automation only.
- Architecture-contract regression tests.

## Hardware commissioning — requires the actual M5 Pro Mac

1. Benchmark installed local models and finalize fast/general/reasoning/coding routes.
2. Measure memory pressure/context behavior under realistic concurrent workloads.
3. Select and benchmark the local multimodal vision model.
4. Select/tune Whisper model and final TTS voice.
5. Tune wake-word sensitivity and acoustic barge-in in the real environment.
6. Validate macOS microphone, accessibility/automation and screen-recording permissions.
7. Validate phone API access over the intended LAN/VPN configuration.
8. Run restart, offline and model-failure recovery tests.
9. Run multi-hour and multi-day daemon soak tests and inspect memory growth/log rotation.
10. Finalize the measured model assignments in `config/local_ai.yaml`.

## Post-commissioning enhancements

- Add MLX and/or llama.cpp adapters if benchmarking shows a material benefit.
- Improve the Presence visual design after runtime state behavior is proven.
- Add additional permission-reviewed external connectors only as actual workflows require them.
- Continue agent specialization using explicit contracts rather than adding autonomous privileges globally.
