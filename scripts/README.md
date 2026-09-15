# `scripts/` — Operator Helpers

This folder contains convenience scripts that call the tested Python implementation rather than duplicating Trinity runtime logic.

- `install_macos.sh` runs macOS preflight, creates a memory backup, and prepares the user LaunchAgent through `core.macos_deployment`.

Review scripts before running them on the production Mac. Scripts must not silently weaken permission/security checks or store secrets in the repository.

## Android pre-hardware test

- `install_android_test.sh` installs the temporary Termux dependencies and builds llama.cpp when needed.
- `start_android_model.sh` starts a local llama.cpp server using the `trinity-phone` model alias.

See `docs/ANDROID_PRE_HARDWARE_TEST.md`.

- `run_android_test.sh` starts the isolated interactive Android acceptance harness.
- `android_doctor.sh` checks phone readiness.
