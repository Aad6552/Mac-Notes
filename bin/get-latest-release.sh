#!/usr/bin/env bash
# Downloads the latest GitHub release of Nexon Notes and installs it over
# this running copy, then relaunches the app.
#
# install.sh deliberately excludes .git when it copies the app into place,
# so this can't "git fetch/reset" like a normal checkout -- it pulls the
# release tarball over HTTP instead and rsyncs it into place.
#
# The app that launches this script quits right after doing so, so all
# progress/errors are written to update.log (next to this script's parent
# dir) instead of a terminal the user could watch.
#
# Usage: bin/get-latest-release.sh
set -e

cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"
LOG_FILE="$APP_DIR/update.log"
GITHUB_REPO="Aad6552/Nexon-Notes"

exec >"$LOG_FILE" 2>&1
echo "Update started: $(date)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Looking up latest release..."
TARBALL_URL="$(curl -fsSL "https://api.github.com/repos/$GITHUB_REPO/releases/latest" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["tarball_url"])')"

if [[ -z "$TARBALL_URL" ]]; then
  echo "Could not determine the latest release download URL." >&2
  exit 1
fi

echo "Downloading $TARBALL_URL"
curl -fsSL "$TARBALL_URL" -o "$TMP_DIR/release.tar.gz"

mkdir -p "$TMP_DIR/extracted"
tar -xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR/extracted" --strip-components=1

echo "Installing into $APP_DIR"
rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'update.log' \
  "$TMP_DIR/extracted"/ "$APP_DIR"/

echo "Update complete: $(tr -d '[:space:]' < "$APP_DIR/VERSION" 2>/dev/null). Relaunching..."
nohup "$APP_DIR/run.sh" >>"$LOG_FILE" 2>&1 &
