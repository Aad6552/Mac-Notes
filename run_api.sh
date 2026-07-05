#!/usr/bin/env bash
# Nexon Notes — REST API launcher (reads/writes the same ~/Notes/notes.db
# as the desktop app)
set -e
cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "Setting up environment (first run only)…"
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install Flask if needed
python3 -c "import flask" 2>/dev/null || {
  echo "Installing Flask…"
  pip install --quiet -r requirements.txt
}

python3 app.py
