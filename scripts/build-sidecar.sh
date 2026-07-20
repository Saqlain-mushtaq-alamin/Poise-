#!/usr/bin/env bash
# Builds the FastAPI backend into a single-file executable with PyInstaller
# and places it in src-tauri/binaries/ using the target-triple naming
# convention Tauri's `externalBin` requires (see src-tauri/tauri.conf.json).
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET_TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
if [[ -z "$TARGET_TRIPLE" ]]; then
  echo "error: could not determine host target triple (is rustc installed?)" >&2
  exit 1
fi

echo "Building sidecar for target: $TARGET_TRIPLE"

cd backend
pip install --quiet -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --name poise-backend \
  --distpath ../src-tauri/binaries \
  --workpath ./build \
  --specpath ./build \
  app/main.py

cd ..

BIN_EXT=""
if [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
  BIN_EXT=".exe"
fi

mv "src-tauri/binaries/poise-backend${BIN_EXT}" \
   "src-tauri/binaries/poise-backend-${TARGET_TRIPLE}${BIN_EXT}"

echo "Sidecar binary ready: src-tauri/binaries/poise-backend-${TARGET_TRIPLE}${BIN_EXT}"
