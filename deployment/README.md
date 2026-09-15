# `deployment/` — Deployment Helpers

The supported production target is macOS on the local Trinity host.

See [`macos/README.md`](macos/README.md) for the complete installation, LaunchAgent, permissions, backup, recovery, and troubleshooting guide.

The authoritative Python deployment implementation is `core/macos_deployment.py`. Platform scripts in this directory are operator conveniences and should call that implementation rather than duplicate deployment logic.
