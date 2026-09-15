#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export TRINITY_PLATFORM_PROFILE=android_termux
export TRINITY_LOCAL_AI_CONFIG="$ROOT/config/android_test.yaml"
python -m core.android_doctor "$@"
