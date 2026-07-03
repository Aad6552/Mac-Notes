#!/usr/bin/env bash
# Mac Notes — native desktop app launcher
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

python3 mac_notes.py
