"""In-app sign-in for Proton Drive / Google Drive / Microsoft OneDrive.

Wires credentials into rclone remotes so cloud_sync.py can back up to them.
For Google/OneDrive this runs `rclone authorize`, which opens the user's
browser straight to the provider's own login page — no password or token
ever passes through this app. For Proton Drive (no browser OAuth in
rclone), it takes an email/password/2FA form and hands it to
`rclone config create` directly.
"""

import re
import subprocess
import threading

from cloud_sync import REMOTE_TYPES, REMOTE_SUBDIR

PROVIDER_TYPES = [('protondrive', REMOTE_TYPES['protondrive']),
                   ('drive', REMOTE_TYPES['drive']),
                   ('onedrive', REMOTE_TYPES['onedrive'])]

DEFAULT_REMOTE_NAMES = {'protondrive': 'proton', 'drive': 'gdrive', 'onedrive': 'onedrive'}
OAUTH_TIMEOUT = 300  # seconds allowed to complete the browser login


def _clear_stale_authorize():
    """Kill any leftover `rclone authorize` process still holding the local
    OAuth callback port from a previous attempt that never finished (app
    closed mid sign-in, crashed, etc). A new attempt always supersedes an
    old abandoned one — otherwise it fails with a confusing
    port-already-in-use error."""
    subprocess.run(['pkill', '-f', 'rclone authorize'],
                    capture_output=True, text=True, timeout=5)


def list_remotes():
    """rclone type -> remote name, for whichever of our 3 provider types
    are already configured."""
    try:
        result = subprocess.run(
            ['rclone', 'listremotes', '--long'],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}
    out = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        name, rtype = line.split(None, 1)
        rtype = rtype.strip()
        if rtype in DEFAULT_REMOTE_NAMES:
            out[rtype] = name.rstrip(':')
    return out


def disconnect(remote_name):
    subprocess.run(['rclone', 'config', 'delete', remote_name],
                    capture_output=True, text=True, timeout=10)


def _make_notes_folder(remote_name):
    subprocess.run(['rclone', 'mkdir', f'{remote_name}:{REMOTE_SUBDIR}'],
                    capture_output=True, text=True, timeout=45)


def login_oauth(rtype, remote_name, on_status=None, on_url=None, on_done=None):
    """Blocking — call from a background thread. Opens the user's browser
    via `rclone authorize` and, on success, wires the resulting token into
    a new remote.

    rclone's own browser-open (via xdg-open in the subprocess) doesn't
    reliably fire from deep inside a background thread of a GUI app, so
    the caller should also try opening `on_url`'s link itself (e.g. via
    QDesktopServices) rather than relying on rclone alone."""
    _clear_stale_authorize()
    try:
        proc = subprocess.Popen(
            ['rclone', 'authorize', rtype, '--auth-no-open-browser'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
    except FileNotFoundError:
        if on_done:
            on_done(False, 'rclone is not installed')
        return

    lines = []
    url_shown = False

    def pump():
        nonlocal url_shown
        for line in proc.stdout:
            lines.append(line)
            m = re.search(r'https?://\S+', line)
            if m and not url_shown:
                url_shown = True
                if on_url:
                    on_url(m.group(0))
                if on_status:
                    on_status('Switch to your browser to finish signing in — '
                               'a tab should already be open (check Alt+Tab '
                               "if it didn't come to the front)")

    pump_thread = threading.Thread(target=pump, daemon=True)
    pump_thread.start()

    try:
        proc.wait(timeout=OAUTH_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        if on_done:
            on_done(False, 'Timed out waiting for browser sign-in')
        return
    pump_thread.join(timeout=2)

    output = ''.join(lines)
    if proc.returncode != 0:
        if on_done:
            on_done(False, 'Sign-in failed or was cancelled')
        return

    token_match = re.search(r'\{.*\}', output, re.S)
    if not token_match:
        if on_done:
            on_done(False, 'Could not read login token from rclone')
        return

    create = subprocess.run(
        ['rclone', 'config', 'create', remote_name, rtype,
         f'token={token_match.group(0)}', '--non-interactive'],
        capture_output=True, text=True, timeout=45,
    )
    if create.returncode != 0:
        if on_done:
            on_done(False, create.stderr.strip() or 'Could not save credentials')
        return

    _make_notes_folder(remote_name)
    if on_done:
        on_done(True, 'Connected')


def login_proton(email, password, twofa, remote_name, on_done=None):
    """Blocking — call from a background thread."""
    args = ['rclone', 'config', 'create', remote_name, 'protondrive',
            f'username={email}', f'password={password}']
    if twofa:
        args.append(f'2fa={twofa}')
    args += ['--non-interactive', '--obscure']

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        if on_done:
            on_done(False, 'Timed out signing in')
        return
    if result.returncode != 0:
        if on_done:
            on_done(False, result.stderr.strip() or 'Sign-in failed — check your credentials')
        return

    _make_notes_folder(remote_name)
    if on_done:
        on_done(True, 'Connected')
