# Nexon Notes

A simple, native-feeling notes app built with PyQt6. Notes are organized into folders, auto-save as you type, and are stored locally in a SQLite database.

## Requirements

### Ubuntu

* Ubuntu 22.04+ (or compatible Linux distribution)
* Python 3.10+

### macOS

* macOS 12+
* Python 3.10+

## Quick Start

```bash
git clone <this-repo> nexon-notes
cd nexon-notes
./run.sh
```

The first run creates a local virtual environment in `.venv/` and installs PyQt6 automatically. Subsequent runs launch the app directly.

## Data Storage

Notes are stored in:

```text
~/Notes/notes.db
```

Every note is also exported as a plain-text file under:

```text
~/Notes/folders
```

The folder structure mirrors the folders shown inside the application.

Notes without a folder are stored in:

```text
~/Notes/folders/All Notes
```

## Installing as a Desktop App

Run:

```bash
./install.sh
```

The installer automatically:

* Installs required dependencies.
* Installs rclone if needed for cloud backups.
* Creates desktop integration for your platform.
* Installs Nexon Notes as a normal desktop application.
* Adds the application icon and launcher.
* Makes Nexon Notes available from your applications menu, launcher, Spotlight, or Launchpad.

Re-run `./install.sh` whenever you update the source code and want the installed version refreshed.

## Uninstalling

Run:

```bash
./install.sh --uninstall
```

If your installer does not support uninstall mode, remove the files installed by `install.sh` manually.

## Cloud Backup

Nexon Notes can back up notes to:

* Proton Drive
* Microsoft OneDrive
* Google Drive
* Dropbox

Click **☁ Manage Cloud Accounts...** in the sidebar to connect accounts.

Backups run automatically in the background and upload:

```text
notes.db
notes/folders/
```

Offline or disconnected providers are skipped automatically.

## Project Layout

```text
nexon_notes.py             Main PyQt6 application
notes_db.py                SQLite storage layer
cloud_sync.py              Background cloud synchronization
cloud_login.py             Creates cloud provider connections
cloud_accounts_dialog.py   Cloud account management dialog
run.sh                     Sets up the environment and starts the app
install.sh                 Desktop installation script
assets/logo.png            Application icon
app.py                     REST API
run_api.sh                 Starts the REST API
```

## REST API

Start the API server:

```bash
./run_api.sh
```

Available endpoints:

```text
GET     /api/notes
POST    /api/notes
PUT     /api/notes
DELETE  /api/notes

GET     /api/folders
GET     /api/search
```

See comments in `app.py` for implementation details.

## Troubleshooting

### PyQt6 Installation Fails

Delete the virtual environment and try again:

```bash
rm -rf .venv
./run.sh
```

### Cloud Sync Not Working

Verify rclone is installed:

```bash
rclone version
```

Then reconnect the affected cloud account from the Cloud Accounts dialog.

### Application Doesn't Appear in the Launcher

Run the installer again:

```bash
./install.sh
```

Then log out and back in if necessary.
