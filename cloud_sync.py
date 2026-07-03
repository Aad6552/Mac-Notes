"""Background cloud backup for Ubuntu Notes.

Uses whatever rclone remotes the user has configured (`rclone config`) to
copy notes.db to Proton Drive, Google Drive, and/or Microsoft OneDrive.
Remotes are matched by *type*, not name, so this keeps working no matter
what the user called them.

If a remote isn't configured, or the user isn't currently logged in to it
(expired token, offline, etc.), that remote is silently skipped — this is
best-effort backup, not a requirement for the app to function.
"""

import os
import subprocess
import threading
import time

REMOTE_TYPES = {
    'protondrive': 'Proton Drive',
    'drive': 'Google Drive',
    'onedrive': 'Microsoft OneDrive',
}

RCLONE_PER_REMOTE_TIMEOUT = 60  # seconds — Proton Drive's handshake can be slow
REMOTE_SUBDIR = 'notes'


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

    def sync_all_and_wait(self, timeout):
        """Blocking variant for shutdown: give the last edits a bounded
        chance to reach the cloud before the process exits and kills any
        in-flight background sync thread. If a sync is already running,
        this doesn't wait for it (avoids a lock-acquire race) — the caller
        should just proceed with shutdown."""
        done = threading.Event()
        self.sync_all_async(on_done=done.set)
        done.wait(timeout=timeout)

    def _sync_all(self, on_done):
        try:
            if not os.path.exists(self.db_path):
                return
            for name, label in self._discover_remotes():
                ok = self._sync_one(name)
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

    def _sync_one(self, remote_name):
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
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
