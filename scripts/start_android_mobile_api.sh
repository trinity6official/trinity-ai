#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! curl -fsS --max-time 2 http://127.0.0.1:8080/v1/models >/dev/null 2>&1 \
   && ! curl -fsS --max-time 2 http://127.0.0.1:8080/api/tags >/dev/null 2>&1; then
  echo "[FAIL] llama-server is not running on 127.0.0.1:8080"
  echo "Start the Trinity phone model first."
  exit 2
fi

if ! python - <<'PY' >/dev/null 2>&1
import fastapi, uvicorn, jose, slowapi, multipart
PY
then
  echo "Installing Android API test dependencies..."
  python -m pip install -r requirements-android-api.txt
fi

read -r -s -p "Choose Trinity app PIN: " TRINITY_PIN
echo
if [[ -z "$TRINITY_PIN" ]]; then
  echo "PIN cannot be empty"
  exit 2
fi

export TRINITY_APP_PIN_HASH="$(printf '%s' "$TRINITY_PIN" | sha256sum | cut -d' ' -f1)"
export TRINITY_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
unset TRINITY_PIN

exec python -m core.android_api_test
