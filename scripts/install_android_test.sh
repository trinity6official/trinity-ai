#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

if [[ "${PREFIX:-}" != *"com.termux"* ]]; then
  echo "This installer must be run inside Termux on Android."
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pkg update -y
pkg install -y python git cmake ninja clang make libandroid-spawn termux-api curl unzip
python -m pip install -r requirements-android-test.txt

SERVER="$(command -v llama-server || true)"
if [[ -z "$SERVER" ]]; then
  if pkg install -y llama-cpp >/dev/null 2>&1; then
    SERVER="$(command -v llama-server || true)"
  fi
fi

if [[ -z "$SERVER" ]]; then
  echo "Building llama.cpp locally (official Termux route)..."
  if [[ ! -d "$HOME/llama.cpp/.git" ]]; then
    git clone --depth=1 https://github.com/ggml-org/llama.cpp "$HOME/llama.cpp"
  else
    git -C "$HOME/llama.cpp" pull --ff-only || true
  fi
  cmake -S "$HOME/llama.cpp" -B "$HOME/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "$HOME/llama.cpp/build" --config Release -t llama-server -j2
  SERVER="$HOME/llama.cpp/build/bin/llama-server"
fi

if [[ ! -x "$SERVER" ]]; then
  echo "llama-server was not installed successfully."
  exit 3
fi

if [[ "$SERVER" != "$PREFIX/bin/llama-server" && ! -e "$PREFIX/bin/llama-server" ]]; then
  ln -s "$SERVER" "$PREFIX/bin/llama-server"
fi

cat <<'EOF'

Android test prerequisites are ready.

Next:
1. Put a small 3B-4B instruct/chat GGUF model in your Termux home directory.
2. Start it:
     ./scripts/start_android_model.sh ~/YOUR_MODEL.gguf
3. Open a second Termux session and run:
     ./scripts/android_doctor.sh
     ./scripts/run_android_test.sh

For voice, install the Termux:API Android app from the SAME source/signing family
as Termux, then grant microphone permission.
EOF
