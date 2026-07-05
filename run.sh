#!/usr/bin/env bash
# Nexon Notes — native desktop app launcher
set -e
cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "Setting up environment (first run only)…"
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install PyQt6 if needed
python3 -c "from PyQt6 import QtWidgets" 2>/dev/null || {
  echo "Installing PyQt6…"
  pip install --quiet PyQt6
}

# macOS only: lets the app rename its menu-bar entry from "Python" to "Nexon Notes"
if [ "$(uname)" = "Darwin" ]; then
  python3 -c "import Foundation" 2>/dev/null || {
    echo "Installing pyobjc-framework-Cocoa…"
    pip install --quiet pyobjc-framework-Cocoa
  }
fi

python3 nexon_notes.py
