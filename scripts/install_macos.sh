#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Trinity macOS installer must be run on macOS." >&2
  exit 1
fi

PYTHON_BIN="${TRINITY_PYTHON:-python3}"
"$PYTHON_BIN" -m core.macos_deployment preflight
"$PYTHON_BIN" -m core.macos_deployment backup
"$PYTHON_BIN" -m core.macos_deployment install

echo
echo "Trinity files are prepared. Review the LaunchAgent before loading it:"
echo "$HOME/Library/LaunchAgents/com.trinity6.trinity-ai.plist"
echo
echo "macOS may ask for Microphone, Accessibility, and Screen Recording permissions"
echo "when you enable voice, computer control, and vision. Trinity does not bypass them."
