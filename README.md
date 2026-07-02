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
git clone <this-repo> ubuntu-notes-1.0
cd ubuntu-notes-1.0
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

This copies the app to `~/.local/share/ubuntu-notes` (alongside where other
user-installed apps on this machine keep their files) and writes a
`.desktop` launcher — with `Exec`/`Icon` pointing at that install
location — to `~/.local/share/applications/ubuntu-notes.desktop`.

Press <kbd>Super</kbd> and type "Ubuntu Notes" — it should appear in the
results. If it doesn't show up right away, log out and back in.

Re-run `./install.sh` any time to pick up changes made in this source
checkout (it resyncs the installed copy and regenerates the launcher).

To uninstall:

```bash
rm ~/.local/share/applications/ubuntu-notes.desktop
rm -rf ~/.local/share/ubuntu-notes
```

## Project layout

```
ubuntu_notes.py       Main PyQt6 application (this is what run.sh launches)
run.sh                Sets up the venv and starts the app
assets/logo.png        App icon
ubuntu-notes.desktop   Desktop launcher entry (see "Installing as a desktop app")
```

`app.py`, `templates/`, and `static/` are an earlier Flask-based web
prototype of the same app, kept for reference — they're not used by
`run.sh` and aren't required for normal use.

## Troubleshooting

- **PyQt6 fails to install**: make sure `python3-venv` and build tools are
  present (`sudo apt install python3-venv python3-dev`), then delete `.venv/`
  and re-run `./run.sh`.
- **App doesn't appear in Activities after installing the `.desktop` file**:
  double-check the `Exec`/`Icon` paths are absolute and correct, then re-run
  `update-desktop-database ~/.local/share/applications`.
