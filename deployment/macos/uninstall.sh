#!/bin/zsh
set -euo pipefail
LABEL="com.trinity6.trinity-ai"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed Trinity launch agent. Memory and project files were left untouched."
