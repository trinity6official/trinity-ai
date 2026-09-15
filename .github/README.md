# `.github/` — CI and Build Automation

GitHub Actions is **not** Trinity's runtime or memory system.

- `workflows/trinity.yml` compiles and tests the local runtime.
- `workflows/build_apk.yml` builds the optional Flutter Android client and requires an explicitly configured Mac-reachable Trinity API URL.

Workflows must never run Trinity's consciousness as a scheduled cloud brain or commit/push runtime memory files.
