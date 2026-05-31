#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Agrandiz"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/$APP_NAME-beta.dmg"
DMG_TEMP="$DIST_DIR/dmg-temp"

if [ ! -d "$APP_PATH" ]; then
  echo "Missing $APP_PATH"
  echo "Run scripts/build_macos_app.sh first."
  exit 1
fi

rm -rf "$DMG_TEMP" "$DMG_PATH"
mkdir -p "$DMG_TEMP"

cp -R "$APP_PATH" "$DMG_TEMP/"
ln -s /Applications "$DMG_TEMP/Applications"

cat > "$DMG_TEMP/README.txt" <<'TXT'
Agrandiz Beta

1. Drag Agrandiz.app to Applications.
2. Open Agrandiz.app.
3. If macOS blocks it, right-click the app and choose Open.
4. If Photos Library cannot be scanned, grant Full Disk Access:
   System Settings > Privacy & Security > Full Disk Access > Agrandiz

All processing is local.
No upload.
No deletion.
TXT

hdiutil create \
  -volname "$APP_NAME Beta" \
  -srcfolder "$DMG_TEMP" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Built: $DMG_PATH"
