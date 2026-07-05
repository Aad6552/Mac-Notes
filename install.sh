#!/usr/bin/env bash
# Installs Nexon Notes for the current user (macOS and Linux):
#   - installs rclone if it isn't already on $PATH (used for cloud backup)
#   - copies the app into a per-user app directory
#   - macOS: registers a Nexon Notes.app launcher in /Applications
#     (Spotlight/Launchpad)
#   - Linux: registers a .desktop launcher in ~/.local/share/applications
#     (app grid / activities search)
set -e

OS="$(uname)"
if [[ "$OS" != "Darwin" && "$OS" != "Linux" ]]; then
  echo "This installer supports macOS and Linux only (detected $OS)." >&2
  exit 1
fi

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(tr -d '[:space:]' < "$SRC_DIR/VERSION" 2>/dev/null || echo "1.0.0")"

if [[ "$OS" == "Darwin" ]]; then
  INSTALL_DIR="$HOME/Library/Application Support/Nexon Notes"
  APP_BUNDLE="/Applications/Nexon Notes.app"
else
  INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nexon-notes"
  DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  DESKTOP_FILE="$DESKTOP_DIR/nexon-notes.desktop"
fi

# --- Linux: system packages run.sh needs to build its venv / run Qt ----------
if [[ "$OS" == "Linux" ]] && command -v apt-get >/dev/null 2>&1; then
  missing=()
  command -v rsync >/dev/null 2>&1        || missing+=(rsync)
  python3 -m venv --help >/dev/null 2>&1  || missing+=(python3-venv)
  # Qt 6.5+ xcb platform plugin needs these at runtime on Ubuntu 22.04+
  ldconfig -p 2>/dev/null | grep -q libxcb-cursor  || missing+=(libxcb-cursor0)
  ldconfig -p 2>/dev/null | grep -q 'libGL\.so'    || missing+=(libgl1)
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Installing system packages: ${missing[*]}"
    if ! sudo apt-get install -y "${missing[@]}"; then
      echo "Warning: could not install ${missing[*]}" >&2
      echo "Install them yourself if the app fails to start." >&2
    fi
  fi
fi

# --- rclone (used for cloud backup) -----------------------------------------
if ! command -v rclone >/dev/null 2>&1; then
  echo "Installing rclone..."
  installed=false
  if [[ "$OS" == "Linux" ]] && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y rclone && installed=true
  else
    sudo -v
    curl https://rclone.org/install.sh | sudo bash && installed=true
  fi
  if [[ "$installed" != true ]]; then
    echo "Warning: rclone install failed" >&2
    echo "Cloud backup will be unavailable until you install rclone yourself" >&2
    echo "(see https://rclone.org/downloads/)." >&2
  fi
fi

mkdir -p "$INSTALL_DIR"

rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  "$SRC_DIR"/ "$INSTALL_DIR"/

chmod +x "$INSTALL_DIR/run.sh"

# =============================================================================
# Linux: register a .desktop launcher and finish
# =============================================================================
if [[ "$OS" == "Linux" ]]; then
  mkdir -p "$DESKTOP_DIR"
  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Nexon Notes
Comment=Simple notes app with folders and cloud backup
Exec="$INSTALL_DIR/run.sh"
Icon=$INSTALL_DIR/assets/logo.png
Terminal=false
Categories=Utility;Office;
StartupWMClass=Nexon Notes
EOF
  chmod 644 "$DESKTOP_FILE"
  command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

  echo "Installed Nexon Notes to $INSTALL_DIR"
  echo "Launcher installed at $DESKTOP_FILE"
  echo "Look for \"Nexon Notes\" in your app grid (log out and back in if it doesn't show up right away)."
  exit 0
fi

# =============================================================================
# macOS: build a Nexon Notes.app bundle in /Applications
# =============================================================================

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
STAGE_BUNDLE="$(mktemp -d)/Nexon Notes.app"
mkdir -p "$STAGE_BUNDLE/Contents/MacOS" "$STAGE_BUNDLE/Contents/Resources"

cat > "$STAGE_BUNDLE/Contents/MacOS/nexon-notes" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/run.sh"
EOF
chmod +x "$STAGE_BUNDLE/Contents/MacOS/nexon-notes"

cp "$INSTALL_DIR/assets/AppIcon.icns" "$STAGE_BUNDLE/Contents/Resources/AppIcon.icns"

cat > "$STAGE_BUNDLE/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Nexon Notes</string>
  <key>CFBundleDisplayName</key>
  <string>Nexon Notes</string>
  <key>CFBundleIdentifier</key>
  <string>com.nexonnotes.app</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>nexon-notes</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

# --- move the bundle into /Applications -------------------------------------
# /Applications is writable by admin users on most Macs; fall back to sudo
# if this account doesn't have direct write access.
if rm -rf "$APP_BUNDLE" 2>/dev/null && cp -R "$STAGE_BUNDLE" "$APP_BUNDLE" 2>/dev/null; then
  :
else
  echo "Need elevated permissions to write to /Applications..."
  sudo rm -rf "$APP_BUNDLE"
  sudo cp -R "$STAGE_BUNDLE" "$APP_BUNDLE"
fi
rm -rf "$(dirname "$STAGE_BUNDLE")"

echo "Installed Nexon Notes to $INSTALL_DIR"
echo "Launcher installed at $APP_BUNDLE"
echo "Look for \"Nexon Notes\" in Spotlight/Launchpad (log out and back in if it doesn't show up right away)."
