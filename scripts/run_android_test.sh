#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export TRINITY_PLATFORM_PROFILE=android_termux
export TRINITY_LOCAL_AI_CONFIG="$ROOT/config/android_test.yaml"
export TRINITY_VOICE_PROVIDER=termux
export TRINITY_API_ENABLED=false
export TRINITY_PRESENCE_ENABLED=false
export TRINITY_TELEGRAM_ENABLED=false
export TRINITY_VOICE_LISTENING_ENABLED=false
exec python -m core.android_test "$@"
