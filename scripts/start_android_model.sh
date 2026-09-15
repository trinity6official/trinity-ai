#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

MODEL="${1:-Qwen/Qwen3-4B-GGUF:Q4_K_M}"
CTX="${2:-4096}"

SERVER="$(command -v llama-server || true)"

if [[ -z "$SERVER" && -x "$HOME/llama.cpp/build/bin/llama-server" ]]; then
  SERVER="$HOME/llama.cpp/build/bin/llama-server"
fi

if [[ -z "$SERVER" ]]; then
  echo "llama-server not found. Run ./scripts/install_android_test.sh first."
  exit 2
fi

COMMON_ARGS=(
  --alias trinity-phone
  --host 127.0.0.1
  --port 8080
  --sleep-idle-seconds 180
  --ctx-size "$CTX"
)

# Explicit local GGUF path.
if [[ "$MODEL" == *.gguf || "$MODEL" == /* || "$MODEL" == ./* || "$MODEL" == ../* ]]; then
  if [[ ! -f "$MODEL" ]]; then
    echo "Model not found: $MODEL"
    exit 2
  fi

  exec "$SERVER" \
    --model "$MODEL" \
    "${COMMON_ARGS[@]}"
else
  # Hugging Face repo:quant form.
  exec "$SERVER" \
    -hf "$MODEL" \
    "${COMMON_ARGS[@]}"
fi
