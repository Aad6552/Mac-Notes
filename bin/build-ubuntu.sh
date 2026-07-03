#!/usr/bin/env bash
# Builds an installable .deb package of Ubuntu Notes for Ubuntu/Debian.
#
# Bundles ubuntu_notes.py and its dependencies into a standalone binary with
# PyInstaller, then wraps that binary in a .deb with a desktop launcher and
# icon. Cloud backup still relies on the `rclone` CLI being on $PATH at
# runtime (same as running from source) — install it separately if you want
# that feature.
#
# Usage: bin/build-ubuntu.sh
# Output: dist/ubuntu-notes_<version>_amd64.deb
set -e

cd "$(dirname "$0")/.."

VERSION="$(tr -d '[:space:]' < VERSION)"
ARCH="amd64"
PKG_NAME="ubuntu-notes"
DIST_DIR="dist"
BUILD_DIR=".build"
BUILD_ROOT="$DIST_DIR/pkgroot"
PKG_DIR="$DIST_DIR/${PKG_NAME}_${VERSION}_${ARCH}"

echo "Building ${PKG_NAME} v${VERSION} for ${ARCH}..."

rm -rf "$BUILD_DIR" "$BUILD_ROOT" "$PKG_DIR"

# --- isolated venv with build tools -----------------------------------------
# A dedicated venv (no --system-site-packages) so PyInstaller freezes a known
# set of deps and `pip install` doesn't hit Debian's externally-managed-
# environment guard. Kept separate from the .venv/ used by run.sh.
python3 -m venv "$BUILD_DIR/venv"
source "$BUILD_DIR/venv/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet PyQt6 pyinstaller

# --- freeze the app with PyInstaller ---------------------------------------
pyinstaller --noconfirm --clean --onefile \
  --name "$PKG_NAME" \
  --distpath "$BUILD_ROOT" \
  --workpath "$BUILD_DIR/work" \
  --specpath "$BUILD_DIR/work" \
  --add-data "$(pwd)/assets/logo.png:assets" \
  ubuntu_notes.py

# --- assemble the .deb tree -------------------------------------------------
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/$PKG_NAME"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/pixmaps"

cp "$BUILD_ROOT/$PKG_NAME" "$PKG_DIR/opt/$PKG_NAME/$PKG_NAME"
chmod 755 "$PKG_DIR/opt/$PKG_NAME/$PKG_NAME"

ln -sf "/opt/$PKG_NAME/$PKG_NAME" "$PKG_DIR/usr/bin/$PKG_NAME"

cp assets/logo.png "$PKG_DIR/usr/share/pixmaps/$PKG_NAME.png"

cat > "$PKG_DIR/usr/share/applications/$PKG_NAME.desktop" <<EOF
[Desktop Entry]
Name=Ubuntu Notes
Comment=Write and organise your notes
Exec=/usr/bin/$PKG_NAME
TryExec=/usr/bin/$PKG_NAME
Icon=$PKG_NAME
Terminal=false
Type=Application
Categories=Utility;TextEditor;
Keywords=notes;notepad;text;
StartupNotify=true
EOF
chmod 644 "$PKG_DIR/usr/share/applications/$PKG_NAME.desktop"

INSTALLED_SIZE="$(du -sk "$PKG_DIR/opt" "$PKG_DIR/usr" | awk '{sum += $1} END {print sum}')"

cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Recommends: rclone
Maintainer: Ubuntu Notes <noreply@example.com>
Description: Simple, native-feeling notes app for Ubuntu/GNOME
 Notes are organized into folders, auto-save as you type, and are stored
 locally in a SQLite database. Optional cloud backup to Proton Drive and
 Microsoft OneDrive via rclone.
EOF

# --- build the .deb ----------------------------------------------------------
dpkg-deb --root-owner-group --build "$PKG_DIR" "$DIST_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"

rm -rf "$BUILD_ROOT" "$PKG_DIR" "$BUILD_DIR"

echo
echo "Built $DIST_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Install with: sudo apt install ./$DIST_DIR/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Uninstall with: sudo apt remove $PKG_NAME"
