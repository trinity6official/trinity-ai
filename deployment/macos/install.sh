#!/bin/zsh
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
PYTHON_BIN="${TRINITY_PYTHON:-$(command -v python3)}"

cd "$ROOT"

"$PYTHON_BIN" -m core.macos_deployment preflight
"$PYTHON_BIN" -m core.macos_deployment backup
"$PYTHON_BIN" -m core.macos_deployment install

LABEL="com.trinity6.trinity-ai"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo
echo "Trinity LaunchAgent prepared at:"
echo "  $PLIST"
echo
echo "This helper does not load the service automatically. Review the plist first."
echo "When ready, follow deployment/macos/README.md to enable it with launchctl."
