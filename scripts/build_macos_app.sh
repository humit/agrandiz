#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Agrandiz"
BUNDLE_ID="org.agrandiz.beta"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_VERSION="$(python3 - <<'PYV'
import json
from pathlib import Path
p = Path("VERSION.json")
if p.exists():
    print(json.loads(p.read_text()).get("version", "0.0.0"))
else:
    print("0.0.0")
PYV
)"
DIST_DIR="$ROOT_DIR/dist"
APP_DIR="$DIST_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
APP_RESOURCES="$RESOURCES/agrandiz"
VENV="$RESOURCES/venv"

echo "Root: $ROOT_DIR"

rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>

    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>

    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>

    <key>CFBundleVersion</key>
    <string>$APP_VERSION</string>

    <key>CFBundleShortVersionString</key>
    <string>$APP_VERSION</string>

    <key>CFBundleExecutable</key>
    <string>agrandiz</string>

    <key>CFBundlePackageType</key>
    <string>APPL</string>

    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>

    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2026 agrandiz</string>
  </dict>
</plist>
PLIST

cat > "$MACOS/agrandiz" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES="$APP_ROOT/Resources"
PY="$RESOURCES/venv/bin/python"
GUI="$RESOURCES/agrandiz/app/agrandiz_gui.py"

exec "$PY" "$GUI"
LAUNCHER

chmod +x "$MACOS/agrandiz"

echo "Copying project files..."
mkdir -p "$APP_RESOURCES"

rsync -a \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  --exclude "cache" \
  --exclude "dist" \
  --exclude "build" \
  "$ROOT_DIR/" "$APP_RESOURCES/"

echo "Creating embedded venv..."
python3 -m venv "$VENV"

echo "Installing requirements..."
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$ROOT_DIR/requirements-macos-app.txt"

echo "Ad-hoc signing app..."
codesign --force --deep --sign - "$APP_DIR" || true

echo "Built: $APP_DIR"
