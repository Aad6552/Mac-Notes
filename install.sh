#!/usr/bin/env bash
# Installs Mac Notes for the current user:
#   - copies the app into ~/Library/Application Support/Mac Notes
#   - registers a Mac Notes.app launcher in ~/Applications (Spotlight/Launchpad)
set -e

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/Library/Application Support/Mac Notes"
APP_BUNDLE="$HOME/Applications/Mac Notes.app"
VERSION="$(tr -d '[:space:]' < "$SRC_DIR/VERSION" 2>/dev/null || echo "1.0.0")"

mkdir -p "$INSTALL_DIR" "$HOME/Applications"

rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  "$SRC_DIR"/ "$INSTALL_DIR"/

chmod +x "$INSTALL_DIR/run.sh"

# --- build the .app icon from assets/logo.png -------------------------------
ICONSET="$(mktemp -d)/AppIcon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$SRC_DIR/assets/logo.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$SRC_DIR/assets/logo.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$INSTALL_DIR/assets/AppIcon.icns"
rm -rf "$(dirname "$ICONSET")"

# --- wrap run.sh in a minimal .app bundle so macOS treats it as a real app --
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cat > "$APP_BUNDLE/Contents/MacOS/mac-notes" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/run.sh"
EOF
chmod +x "$APP_BUNDLE/Contents/MacOS/mac-notes"

cp "$INSTALL_DIR/assets/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"

cat > "$APP_BUNDLE/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Mac Notes</string>
  <key>CFBundleDisplayName</key>
  <string>Mac Notes</string>
  <key>CFBundleIdentifier</key>
  <string>com.macnotes.app</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>mac-notes</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

echo "Installed Mac Notes to $INSTALL_DIR"
echo "Launcher installed at $APP_BUNDLE"
echo "Look for \"Mac Notes\" in Spotlight/Launchpad (log out and back in if it doesn't show up right away)."
