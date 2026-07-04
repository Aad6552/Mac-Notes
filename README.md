# Mac Notes

A simple, native-feeling notes app for macOS, built with PyQt6. Notes are
organized into folders, auto-save as you type, and are stored locally in a
SQLite database.

## Requirements

- macOS 12+
- Python 3.10+ (from [python.org](https://python.org) or `brew install python`)

## Quick start

```bash
git clone <this-repo> mac-notes
cd mac-notes
./run.sh
```

The first run creates a local virtual environment in `.venv/` and installs
PyQt6 into it automatically. Subsequent runs just launch the app.

Your notes are stored in `~/Notes/notes.db` (SQLite), independent of where
you check out this repo. Every note is also kept as a plain-text file under
`~/Notes/folders`, laid out to mirror the app's own folders (e.g. a "Work"
folder in the app becomes a "Work" folder there), so you can read your
notes without the app or a SQLite viewer. Notes without a matching folder —
or all notes, if you have none — land in `~/Notes/folders/All Notes`.

## Installing as a desktop app

macOS only. Run the installer:

```bash
./install.sh
```

This installs Mac Notes for your user account by:

- installing [rclone](https://rclone.org) via Homebrew if it isn't already
  on `$PATH` (needed for cloud backup; skipped with a warning if Homebrew
  itself isn't installed)
- copying this app folder to `~/Library/Application Support/Mac Notes`
- building `Mac Notes.app` and moving it into `/Applications`, wrapping
  `run.sh` with a proper icon and `Info.plist`

The original project folder is not deleted or moved. It is copied into the
local app directory so macOS can launch it like a normal app.

Moving the built app into `/Applications` normally doesn't require a
password on admin accounts; if your account can't write there directly, the
installer falls back to `sudo` and will prompt for your password.

Press <kbd>Cmd</kbd>+<kbd>Space</kbd> and type "Mac Notes" — it should
appear in Spotlight/Launchpad. If it doesn't show up right away, log out and
back in.

Re-run `./install.sh` any time to pick up changes made in this source
checkout. It resyncs the installed copy and rebuilds the app bundle.

To uninstall:

```bash
sudo rm -rf /Applications/"Mac Notes.app"
rm -rf ~/Library/"Application Support"/"Mac Notes"
```

## Building a standalone binary

```bash
bin/build-macos.sh
```

Freezes the app with PyInstaller into a self-contained `Mac Notes.app` (no
Python/PyQt6 install required on the target machine) and wraps it in a
drag-to-install `dist/Mac-Notes-<version>.dmg`. Must be run on macOS.

The build is unsigned and not notarized — on first launch, right-click the
app and choose "Open" to get past Gatekeeper's warning.

## Cloud backup

Mac Notes can back up `notes.db` to **Proton Drive**, **Microsoft
OneDrive**, and/or **Google Drive**. Click **☁ Manage Cloud Accounts…** at
the bottom of the sidebar to sign in:

- **OneDrive** / **Google Drive** — click Connect, your browser opens
  straight to the provider's own login page. Nothing passes through the
  app; it just picks up the resulting token once you approve access.
- **Proton Drive** — click Connect and enter your email, password, and (if
  enabled) 2FA code in the form that appears.
- Click **Disconnect** any time to stop backing up to that drive and
  forget its credentials.

Behind the scenes this is all powered by [rclone](https://rclone.org)
remotes (`cloud_login.py` creates them, `cloud_sync.py` uses them).
`install.sh` installs it via Homebrew automatically; if you're running from
source without the installer, get it yourself with `brew install rclone`.

- A backup runs shortly after launch, ~10s after you stop typing, every 5
  seconds in the background, and once more on quit.
- If you're logged out or offline, that drive is silently skipped —
  best-effort backup, not a requirement to use the app.
- Files land in a `notes` folder on each connected drive: `notes.db` plus a
  `notes/folders` folder that mirrors the local `~/Notes/folders` export
  described above.
- Status shows at the bottom of the sidebar, e.g. `☁ Proton Drive ✓ 14:32`.

You can also do this from the terminal with `rclone config` instead of the
in-app dialog — either way ends up creating the same kind of rclone remote.

## Project layout

```
mac_notes.py             Main PyQt6 application (this is what run.sh launches)
notes_db.py              Shared SQLite layer (~/Notes/notes.db) used by the app and the API
cloud_sync.py            Background rclone backup to Proton Drive/OneDrive/Google Drive
cloud_login.py           In-app sign-in — creates the rclone remotes cloud_sync.py uses
cloud_accounts_dialog.py "Manage Cloud Accounts" dialog (PyQt6)
run.sh                   Sets up the venv and starts the app
install.sh               macOS installer: installs rclone, copies the app to ~/Library/Application Support, and builds/moves the .app launcher into /Applications
bin/build-macos.sh       Freezes the app with PyInstaller into a standalone .app/.dmg
assets/logo.png          App icon used by the installed launcher
app.py                   REST API over the same notes.db — see below
run_api.sh               Sets up the venv and starts the API
```

`templates/` and `static/` are an earlier Flask-based web prototype's
frontend, kept for reference — not wired to any route in `app.py` and not
required for normal use.

## REST API

`app.py` exposes the same notes over HTTP for scripting/integrations —
`GET/POST/PUT/DELETE /api/notes`, `/api/folders`, `/api/search`. Run it
with `./run_api.sh`; see the comments at the top of `app.py` for details.

## Troubleshooting

- **PyQt6 fails to install**: make sure Xcode Command Line Tools are
  installed (`xcode-select --install`), then delete `.venv/` and re-run
  `./run.sh`.
- **"Mac Notes" is damaged / can't be opened / unidentified developer**:
  the app is unsigned. Right-click it and choose "Open" instead of
  double-clicking, then confirm in the dialog that appears.
- **App doesn't appear in Spotlight after installing**: double-check
  `/Applications/Mac Notes.app` exists, then log out and back in (or run
  `mdimport /Applications/"Mac Notes.app"`).
