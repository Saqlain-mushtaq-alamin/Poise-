#!/usr/bin/env bash
# scripts/notarize-macos.sh
# Phase 9.3 — manual notarization helper for local testing.
# CI (release.yml) does this automatically via tauri-action; use this
# script only when debugging a signing/notarization issue locally.
#
# Usage: ./scripts/notarize-macos.sh path/to/Poise.app
set -euo pipefail

APP_PATH="${1:?Usage: notarize-macos.sh path/to/Poise.app}"
ZIP_PATH="${APP_PATH%.app}.zip"

: "${APPLE_ID:?Set APPLE_ID}"
: "${APPLE_PASSWORD:?Set APPLE_PASSWORD (app-specific password)}"
: "${APPLE_TEAM_ID:?Set APPLE_TEAM_ID}"
: "${APPLE_SIGNING_IDENTITY:?Set APPLE_SIGNING_IDENTITY}"

echo "==> Signing $APP_PATH"
codesign --deep --force --verify --verbose \
  --sign "$APPLE_SIGNING_IDENTITY" \
  --options runtime \
  --entitlements src-tauri/entitlements.plist \
  "$APP_PATH"

echo "==> Zipping for notarization"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo "==> Submitting to Apple notary service (this can take a few minutes)"
xcrun notarytool submit "$ZIP_PATH" \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait

echo "==> Stapling ticket"
xcrun stapler staple "$APP_PATH"

echo "==> Verifying Gatekeeper acceptance"
spctl --assess --type execute --verbose "$APP_PATH"

echo "Done. $APP_PATH is signed, notarized, and stapled."
