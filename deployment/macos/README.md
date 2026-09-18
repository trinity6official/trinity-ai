# Trinity AI — macOS Deployment Guide

This is the production deployment guide for the local Trinity host. The target design assumes an **Apple Silicon Mac mini (M6, 32 GB unified memory)** running Trinity continuously.

The Mac is Trinity's authoritative runtime. Ollama runs local models; Memory Vault data stays local; mobile/API, Presence and local voice are interfaces to the same runtime.

## 1. Before you start

Recommended prerequisites:

- macOS on Apple Silicon.
- Python 3.11 or newer.
- Ollama installed and runnable locally.
- Enough local disk space for model weights, logs, backups, and memory growth.
- `ffmpeg` if continuous microphone capture is enabled.
- macOS `say`, `osascript`, and `screencapture` are used when the related local features are enabled.

Do not copy API tokens or secrets into the repository.

## 2. Put Trinity in a stable location

Choose a permanent path, for example:

```bash
mkdir -p ~/AI
cd ~/AI
unzip trinity-ai-final.zip
cd trinity-ai
```

Do not install the final always-on service from a temporary Downloads path that you plan to move later. The LaunchAgent stores the project working directory and Python path.

## 3. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
```

Optional local speech dependencies are intentionally not forced by `requirements.txt`. Install the STT stack selected during M6 commissioning (for example local Whisper and its PyTorch dependencies) only after choosing the final configuration.

## 4. Install Ollama and models

Install/start Ollama and confirm it responds locally. Then install candidate models that match `config/local_ai.yaml` or update the YAML to match the models you intend to test.

Trinity expects Ollama at:

```text
http://127.0.0.1:11434
```

unless `LOCAL_LLM_URL` overrides it.

The checked-in Qwen routes are starting points, not final production selections.

## 5. Configure local routes

Edit `config/local_ai.yaml` or use environment overrides:

```bash
export LOCAL_LLM_URL=http://127.0.0.1:11434
export TRINITY_FAST_MODEL=<installed-fast-model>
export TRINITY_GENERAL_MODEL=<installed-general-model>
export TRINITY_REASONING_MODEL=<installed-reasoning-model>
export TRINITY_CODING_MODEL=<installed-coding-model>
export TRINITY_VISION_MODEL=<optional-installed-vision-model>
```

Run the benchmark harness on the actual M6 before making the routes permanent:

```bash
python -m core.model_benchmark --task fast --runs 3
python -m core.model_benchmark --task general --runs 3
python -m core.model_benchmark --task reasoning --runs 3
python -m core.model_benchmark --task coding --runs 3
```

Evaluate quality as well as speed. The benchmark reports time-to-first-token, latency, and approximate throughput; it intentionally does not declare a winner based only on tokens/second.

## 6. Configure optional interfaces/features

### API/mobile access

Use the authenticated local API/mobile client for phone access. Keep the API on loopback by default. Before non-loopback phone access, generate a salted app-PIN verifier with `python scripts/generate_app_pin_hash.py`, configure a strong JWT secret, remove wildcard CORS, and select either HTTPS/TLS or a specifically bound encrypted-VPN interface.

### Local continuous voice

Enable only after local STT/capture is installed and the microphone is validated:

```bash
export TRINITY_VOICE_LISTENING_ENABLED=true
```

Wake-word/session handling is implemented, but final audio tuning should be done on the physical Mac.

### Vision/screen awareness

Configure an installed local vision model with `TRINITY_VISION_MODEL`. Screen awareness should remain off until Screen Recording permission is granted and the privacy behavior is validated.

## 7. Run preflight

```bash
python -m core.macos_deployment preflight
```

Required checks:

- macOS
- Python 3.11+
- Ollama executable
- AppleScript (`osascript`)

Optional checks include macOS speech (`say`), `ffmpeg` microphone capture, and `screencapture`.

## 8. Run Trinity Doctor

```bash
python -m core.doctor
```

For machine-readable output:

```bash
python -m core.doctor --json
```

Doctor checks:

- preflight prerequisites
- Ollama reachability
- installed model coverage for fast/general/reasoning/coding routes
- Memory Vault writability
- API exposure/security posture
- API/mobile security configuration
- optional local voice dependency readiness
- optional vision model availability

Do not enable the always-on service until required Doctor checks are green.

## 9. Test Trinity manually first

```bash
python -m core.run --mode daemon
```

Validate normal conversation, memory writes/recall, local model calls, permissions, approvals, and the channels you intend to use.

Stop it cleanly before installing launchd.

## 10. Create a memory backup

Before changing deployment state:

```bash
python -m core.macos_deployment backup
```

Backups contain Trinity memory/vault data only. Model weights, caches, `.env`, credentials, and secrets are excluded.

SQLite is backed up through SQLite's backup API so committed WAL transactions are captured consistently.

## 11. Prepare the LaunchAgent

Preferred helper:

```bash
./scripts/install_macos.sh
```

Equivalent Python command:

```bash
python -m core.macos_deployment install
```

This creates:

```text
~/Library/LaunchAgents/com.trinity6.trinity-ai.plist
```

The Python helper intentionally **does not load it automatically**. Review the plist first, especially:

- Python executable path
- Working directory
- log paths
- environment flags

The generated service runs:

```text
python -m core.run --mode daemon
```

## 12. Enable the LaunchAgent

After reviewing the plist:

```bash
LABEL=com.trinity6.trinity-ai
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
```

Check status:

```bash
launchctl print "gui/$(id -u)/com.trinity6.trinity-ai"
```

Logs are written under:

```text
<project>/logs/trinity.out.log
<project>/logs/trinity.err.log
```

Follow them with:

```bash
tail -f logs/trinity.out.log logs/trinity.err.log
```

## 13. macOS privacy permissions

macOS remains the final authority. Trinity does not and should not bypass these permissions.

Depending on enabled capabilities, grant access under **System Settings → Privacy & Security**:

- **Microphone** — continuous local voice capture.
- **Accessibility** — UI automation/type/click actions.
- **Automation** — Apple Events/controlling supported apps.
- **Screen Recording** — screen capture and screen-awareness analysis.

Grant only the permissions you actually need.

## 14. Stop or uninstall the service

Stop/remove the LaunchAgent without deleting Trinity data:

```bash
./deployment/macos/uninstall.sh
```

or manually:

```bash
launchctl bootout "gui/$(id -u)/com.trinity6.trinity-ai"
rm -f "$HOME/Library/LaunchAgents/com.trinity6.trinity-ai.plist"
```

Memory and project files remain untouched.

## 15. Backup and restore operations

Create a backup:

```bash
python -m core.macos_deployment backup
```

Create in a different backup directory:

```bash
python -m core.macos_deployment backup --output-dir /path/to/backups
```

Restore is intentionally blocked without explicit approval:

```bash
python -m core.macos_deployment restore /path/to/trinity-memory-....tar.gz
```

Approved restore:

```bash
python -m core.macos_deployment restore /path/to/trinity-memory-....tar.gz --approve
```

Stop Trinity before a production restore, verify the archive source, restore, then run Doctor and start Trinity again.

## 16. Updates

For future code updates:

1. Create a memory backup.
2. Stop the LaunchAgent.
3. Update the code in the stable project directory.
4. Activate `.venv` and update dependencies if required.
5. Run `python -m pytest -q`.
6. Run `python -m core.doctor`.
7. Re-run `python -m core.macos_deployment install` if the Python path or project directory changed.
8. Restart the LaunchAgent.
9. Watch logs and verify memory/voice/API behavior.

## 17. Troubleshooting

### Ollama unavailable

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
python -m core.doctor
```

Confirm the configured models actually appear in `ollama list`.

### LaunchAgent does not start

```bash
launchctl print "gui/$(id -u)/com.trinity6.trinity-ai"
cat logs/trinity.err.log
```

Most failures come from an incorrect Python path, moved project directory, missing dependencies, or environment variables that were only set in an interactive shell.

### Environment variables under launchd

A LaunchAgent does not automatically inherit every variable from your interactive Terminal session. Prefer non-secret checked-in defaults for ordinary configuration and deliberately inject secrets/environment values using a secure local mechanism. Do not put secrets in Git.

### Voice enabled but no transcription

Check macOS Microphone permission, `ffmpeg`, the chosen local STT package/model, and input-device availability. Run voice tests manually before relying on daemon mode.

### Screen awareness fails

Check Screen Recording permission and verify the configured local vision model is installed/reachable.

### Computer automation fails

Check Accessibility and Automation permissions. Permission-gated Trinity actions may also be waiting for explicit approval.

### API works locally but not from phone

Verify the bind address, PBKDF2 PIN verifier, JWT secret, transport mode, CORS policy, firewall, and HTTPS/VPN route. Do not solve connectivity by disabling Trinity's API security checks.

## 18. Production acceptance checklist

Before calling the M6 host production-ready:

- [ ] Full test suite passes locally.
- [ ] `python -m core.doctor` reports READY for required checks.
- [ ] Final local model routes are benchmarked and quality-reviewed.
- [ ] Memory backup and approved restore have been tested.
- [ ] Restart/logout/login behavior has been validated with launchd.
- [ ] Microphone permission and voice sessions are stable, if enabled.
- [ ] Accessibility/Automation actions work only after approval, if enabled.
- [ ] Screen Recording/vision behavior is validated, if enabled.
- [ ] Mobile/API access works through the intended HTTPS or encrypted-VPN path, if enabled.
- [ ] API/mobile and local voice use the same Trinity runtime and message pipeline.
- [ ] Multi-hour/multi-day soak testing has been completed.
