#!/usr/bin/env bash
# Installs Ubuntu Notes for the current user:
#   - copies the app into ~/.local/share/ubuntu-notes
#   - registers the .desktop launcher in ~/.local/share/applications
set -e

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/ubuntu-notes"
APPLICATIONS_DIR="$HOME/.local/share/applications"

mkdir -p "$INSTALL_DIR" "$APPLICATIONS_DIR"

rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  "$SRC_DIR"/ "$INSTALL_DIR"/

chmod +x "$INSTALL_DIR/run.sh"

sed \
  -e "s|^Exec=.*|Exec=$INSTALL_DIR/run.sh|" \
  -e "s|^Icon=.*|Icon=$INSTALL_DIR/assets/logo.png|" \
  "$SRC_DIR/ubuntu-notes.desktop" > "$APPLICATIONS_DIR/ubuntu-notes.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR"
fi

echo "Installed Ubuntu Notes to $INSTALL_DIR"
echo "Launcher installed at $APPLICATIONS_DIR/ubuntu-notes.desktop"
