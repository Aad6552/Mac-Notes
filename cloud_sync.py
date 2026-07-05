"""Background cloud backup for Nexon Notes.

Uses whatever rclone remotes the user has configured (`rclone config`) to
copy notes.db to Proton Drive, Microsoft OneDrive, Google Drive, and/or
Dropbox. Remotes are matched by *type*, not name, so this keeps working no
matter what the user called them.

Alongside notes.db, every note is also exported as a plain-text file under
a folder layout that mirrors the app's own folders (e.g. a "Work" folder
in the app becomes a "Work" folder on the drive holding its notes). Notes
whose folder no longer exists — or all notes, if the app has no folders at
all — land in a catch-all "All Notes" folder instead. This export lives
locally at ~/Notes/folders (regenerated on every pass) and is then pushed
out to each connected cloud remote as-is.

If a remote isn't configured, or the user isn't currently logged in to it
(expired token, offline, etc.), that remote is silently skipped — this is
best-effort backup, not a requirement for the app to function.
"""

import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from urllib.parse import quote

REMOTE_TYPES = {
    'protondrive': 'Proton Drive',
    'onedrive': 'Microsoft OneDrive',
    'drive': 'Google Drive',
    'dropbox': 'Dropbox',
}

RCLONE_PER_REMOTE_TIMEOUT = 60  # seconds — Proton Drive's handshake can be slow
REMOTE_SUBDIR = 'notes'
EXPORT_SUBDIR = 'folders'  # per-folder note exports, alongside notes.db
ALL_NOTES_FOLDER = 'All Notes'


class CloudSync:
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.status = {}  # label -> {'ok': bool, 'when': str}

    def sync_all_async(self, on_done=None):
        """Kick off a backup pass in the background. No-op if one is
        already running or rclone isn't installed."""
        if not self._lock.acquire(blocking=False):
            return
        thread = threading.Thread(
            target=self._sync_all, args=(on_done,), daemon=True
        )
        thread.start()

    def _sync_all(self, on_done):
        try:
            if not os.path.exists(self.db_path):
                return
            export_dir = self._export_notes_by_folder()
            for name, label in self._discover_remotes():
                ok = self._sync_one(name, export_dir)
                self.status[label] = {'ok': ok, 'when': time.strftime('%H:%M')}
        finally:
            self._lock.release()
            if on_done:
                on_done()

    def _discover_remotes(self):
        try:
            result = subprocess.run(
                ['rclone', 'listremotes', '--long'],
                capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []

        remotes = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            name, rtype = line.split(None, 1)
            label = REMOTE_TYPES.get(rtype.strip())
            if label:
                remotes.append((name.rstrip(':'), label))
        return remotes

    def _export_notes_by_folder(self):
        """Regenerate ~/Notes/folders (a sibling of notes.db) laid out as
        <folder>/<note>.txt, mirroring the app's own folders, and return its
        path. Notes whose folder doesn't exist (or every note, if there are
        no folders at all) go under ALL_NOTES_FOLDER instead. This is the
        local, human-readable copy of your notes, and also what gets pushed
        out to each cloud remote."""
        export_root = os.path.join(os.path.dirname(self.db_path), EXPORT_SUBDIR)
        try:
            con = sqlite3.connect(f'file:{quote(self.db_path)}?mode=ro', uri=True)
            con.row_factory = sqlite3.Row
            folder_names = {r['name'] for r in con.execute('SELECT name FROM folders')}
            notes = con.execute('SELECT id, title, content, folder FROM notes').fetchall()
            con.close()
        except sqlite3.Error:
            return export_root if os.path.isdir(export_root) else None

        shutil.rmtree(export_root, ignore_errors=True)
        for note in notes:
            folder = note['folder'] if note['folder'] in folder_names else ALL_NOTES_FOLDER
            folder_dir = os.path.join(export_root, self._safe_name(folder))
            os.makedirs(folder_dir, exist_ok=True)
            filename = f"{note['id']:04d} - {self._safe_name(note['title'] or 'New Note')}.txt"
            with open(os.path.join(folder_dir, filename), 'w', encoding='utf-8') as f:
                f.write(note['content'] or '')
        return export_root

    @staticmethod
    def _safe_name(name):
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '-', name).strip(' .')
        return name[:120] or 'untitled'

    def _sync_one(self, remote_name, export_dir):
        dest = f'{remote_name}:{REMOTE_SUBDIR}/notes.db'
        try:
            # Recreate the "notes" folder if it's been deleted/renamed on the
            # drive since the last sync — copyto alone usually implies this,
            # but backends vary, so make it explicit rather than assumed.
            subprocess.run(
                ['rclone', 'mkdir', f'{remote_name}:{REMOTE_SUBDIR}'],
                capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                ['rclone', 'copyto', self.db_path, dest, '--timeout', '45s'],
                capture_output=True, text=True,
                timeout=RCLONE_PER_REMOTE_TIMEOUT,
            )
            if result.returncode != 0:
                return False
            if not export_dir:
                return True
            folders_result = subprocess.run(
                ['rclone', 'sync', export_dir,
                 f'{remote_name}:{REMOTE_SUBDIR}/{EXPORT_SUBDIR}', '--timeout', '45s'],
                capture_output=True, text=True,
                timeout=RCLONE_PER_REMOTE_TIMEOUT,
            )
            return folders_result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
