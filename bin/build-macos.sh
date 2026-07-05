#!/usr/bin/env bash
# Builds an installable macOS binary of Nexon Notes.
#
# Bundles nexon_notes.py and its dependencies into a standalone Nexon Notes.app
# with PyInstaller, then wraps that .app in a .dmg you can drag into
# /Applications. Cloud backup still relies on the `rclone` CLI being on
# $PATH at runtime (same as running from source) — install it separately
# (e.g. `brew install rclone`) if you want that feature.
#
# Must be run on macOS — it uses sips, iconutil, and hdiutil, none of which
# exist on Linux/Windows.
#
# This build is unsigned/not notarized. On first launch, Gatekeeper will
# block it — right-click the app, choose "Open", then confirm.
#
# Usage: bin/build-macos.sh
# Output: dist/Nexon Notes-<version>.dmg
set -e

cd "$(dirname "$0")/.."

VERSION="$(tr -d '[:space:]' < VERSION)"
APP_NAME="Nexon Notes"
DIST_DIR="dist"
BUILD_DIR=".build"
DMG_STAGE="$BUILD_DIR/dmg-stage"
DMG_PATH="$DIST_DIR/Nexon-Notes-${VERSION}.dmg"

echo "Building ${APP_NAME} v${VERSION} for macOS..."

rm -rf "$BUILD_DIR" "$DIST_DIR/$APP_NAME.app" "$DMG_PATH"
mkdir -p "$DIST_DIR"

# --- isolated venv with build tools -----------------------------------------
python3 -m venv "$BUILD_DIR/venv"
source "$BUILD_DIR/venv/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet PyQt6 pyinstaller

# --- build the .icns app icon from assets/logo.png --------------------------
ICONSET="$BUILD_DIR/AppIcon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" assets/logo.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" assets/logo.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$BUILD_DIR/AppIcon.icns"

# --- freeze the app with PyInstaller ----------------------------------------
# --windowed on macOS always produces a NAME.app bundle, even with --onefile.
pyinstaller --noconfirm --clean --onefile --windowed \
  --name "$APP_NAME" \
  --icon "$(pwd)/$BUILD_DIR/AppIcon.icns" \
  --osx-bundle-identifier "com.nexonnotes.app" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR/work" \
  --specpath "$BUILD_DIR/work" \
  --add-data "$(pwd)/assets/logo.png:assets" \
  nexon_notes.py

# --- wrap the .app in a drag-to-install .dmg --------------------------------
mkdir -p "$DMG_STAGE"
cp -R "$DIST_DIR/$APP_NAME.app" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Applications"

hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGE" -ov -format UDZO "$DMG_PATH" >/dev/null

rm -rf "$BUILD_DIR" "$DIST_DIR/$APP_NAME.app"

echo
echo "Built $DMG_PATH"
echo "Install by opening it and dragging \"$APP_NAME\" into Applications."
echo "First launch: right-click the app -> Open (unsigned build, Gatekeeper will warn once)."
