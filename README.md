# Ubuntu Notes

A simple, native-feeling notes app for Ubuntu/GNOME, built with PyQt6. Notes are
organized into folders, auto-save as you type, and are stored locally in a
SQLite database.

## Requirements

- Linux with a desktop environment (tested on Ubuntu/GNOME)
- Python 3.10+
- `python3-venv` (usually preinstalled; if not: `sudo apt install python3-venv`)

## Quick start

```bash
git clone <this-repo> ubuntu-notes
cd ubuntu-notes
./run.sh
```

The first run creates a local virtual environment in `.venv/` and installs
PyQt6 into it automatically. Subsequent runs just launch the app.

Your notes are stored in `~/Notes/notes.db` (SQLite), independent of where
you check out this repo.

## Installing as a desktop app

Run the installer (no `sudo` needed):

```bash
./install.sh
```

This installs Ubuntu Notes for your user account by:

- copying this app folder to `~/.local/share/ubuntu-notes`
- creating the app launcher at `~/.local/share/applications/ubuntu-notes.desktop`
- pointing the launcher to `~/.local/share/ubuntu-notes/run.sh`
- pointing the app icon to `~/.local/share/ubuntu-notes/assets/logo.png`

The original project folder is not deleted or moved. It is copied into the
local app directory so Ubuntu/GNOME can launch it like a normal app.

Press <kbd>Super</kbd> and type "Ubuntu Notes" — it should appear in the
results. If it doesn't show up right away, log out and back in.

Re-run `./install.sh` any time to pick up changes made in this source
checkout. It resyncs the installed copy and regenerates the launcher with the
correct full paths.

To uninstall:

```bash
rm ~/.local/share/applications/ubuntu-notes.desktop
rm -rf ~/.local/share/ubuntu-notes
```

## Cloud backup

Ubuntu Notes can back up `notes.db` to **Proton Drive** and/or **Microsoft
OneDrive**. Click **☁ Manage Cloud Accounts…** at the bottom of the sidebar
to sign in:

- **OneDrive** — click Connect, your browser opens straight to Microsoft's
  own login page. Nothing passes through the app; it just picks up the
  resulting token once you approve access.
- **Proton Drive** — click Connect and enter your email, password, and (if
  enabled) 2FA code in the form that appears.
- Click **Disconnect** any time to stop backing up to that drive and
  forget its credentials.

Behind the scenes this is all powered by [rclone](https://rclone.org)
remotes (`cloud_login.py` creates them, `cloud_sync.py` uses them):

- A backup runs shortly after launch, ~10s after you stop typing, and every
  3 minutes in the background.
- If you're logged out or offline, that drive is silently skipped —
  best-effort backup, not a requirement to use the app.
- Files land in a `notes/notes.db` folder on each connected drive.
- Status shows at the bottom of the sidebar, e.g. `☁ Proton Drive ✓ 14:32`.

You can also do this from the terminal with `rclone config` instead of the
in-app dialog — either way ends up creating the same kind of rclone remote.

## Project layout

```
ubuntu_notes.py          Main PyQt6 application (this is what run.sh launches)
notes_db.py              Shared SQLite layer (~/Notes/notes.db) used by the app and the API
cloud_sync.py            Background rclone backup to Proton Drive/OneDrive
cloud_login.py           In-app sign-in — creates the rclone remotes cloud_sync.py uses
cloud_accounts_dialog.py "Manage Cloud Accounts" dialog (PyQt6)
run.sh                   Sets up the venv and starts the app
install.sh               Copies the app to ~/.local/share and registers the launcher/icon
assets/logo.png          App icon used by the installed launcher
ubuntu-notes.desktop     Desktop launcher for running from this project folder
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

- **PyQt6 fails to install**: make sure `python3-venv` and build tools are
  present (`sudo apt install python3-venv python3-dev`), then delete `.venv/`
  and re-run `./run.sh`.
- **App doesn't appear in Activities after installing the `.desktop` file**:
  double-check the `Exec`/`Icon` paths are absolute and correct, then re-run
  `update-desktop-database ~/.local/share/applications`.
