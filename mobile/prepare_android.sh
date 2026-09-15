#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f android/gradlew && -f android/app/build.gradle* ]]; then
  echo "Flutter Android scaffold already present."
  exit 0
fi

if ! command -v flutter >/dev/null 2>&1; then
  echo "flutter is required to generate the Android platform scaffold" >&2
  exit 2
fi

manifest="android/app/src/main/AndroidManifest.xml"
tmp_manifest=""
if [[ -f "$manifest" ]]; then
  tmp_manifest="$(mktemp)"
  cp "$manifest" "$tmp_manifest"
fi

flutter create --platforms=android --org com.trinity6 .

if [[ -n "$tmp_manifest" ]]; then
  cp "$tmp_manifest" "$manifest"
  rm -f "$tmp_manifest"
fi

echo "Android scaffold ready."
