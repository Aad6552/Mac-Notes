"""In-app sign-in for Proton Drive / Microsoft OneDrive / Google Drive / Dropbox.

Wires credentials into rclone remotes so cloud_sync.py can back up to them.
For OneDrive, Google Drive, and Dropbox this runs `rclone authorize`, which
opens the user's browser straight to the provider's own login page — no
password or token ever passes through this app. For Proton Drive (no
browser OAuth in rclone), it takes an email/password/2FA form and hands it
to `rclone config create` directly.
"""

import json
import re
import subprocess
import threading

from cloud_sync import REMOTE_TYPES, REMOTE_SUBDIR

PROVIDER_TYPES = [('protondrive', REMOTE_TYPES['protondrive']),
                   ('onedrive', REMOTE_TYPES['onedrive']),
                   ('drive', REMOTE_TYPES['drive']),
                   ('dropbox', REMOTE_TYPES['dropbox'])]

DEFAULT_REMOTE_NAMES = {'protondrive': 'proton', 'onedrive': 'onedrive',
                         'drive': 'gdrive', 'dropbox': 'dropbox'}
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


def _pick_drive_example(option):
    """For the OneDrive "which drive?" question: prefer the one literally
    labeled the user's main personal OneDrive, falling back to whatever
    rclone suggests as the default."""
    for ex in (option.get('Examples') or []):
        if (ex.get('Help') or '').strip().lower() == 'onedrive (personal)':
            return ex['Value']
    return option.get('Default')


def _answer_for(option):
    name = option.get('Name', '')
    if name == 'config_refresh_token':
        return 'false'  # we just got a token — keep it, don't re-auth
    if name == 'config_driveid':
        return _pick_drive_example(option)
    # config_type ("onedrive" vs sharepoint/etc), config_change_team_drive
    # (Google Drive), config_drive_ok, and anything else: rclone's own
    # default is the sane choice.
    default = option.get('Default', '')
    if isinstance(default, bool):
        # rclone's non-interactive protocol matches bool answers against
        # lowercase "true"/"false" literals — Python's str(bool) capitalizes
        # ("True"/"False"), which it doesn't recognize and silently treats
        # as unanswered, falling back to whatever branch its own internal
        # default takes (which for config_refresh_token-like confirmations
        # can mean restarting the browser OAuth step instead of finishing).
        return 'true' if default else 'false'
    return str(default)


def _finish_config_questions(remote_name, response_json):
    """Some backends (OneDrive is the main one) ask follow-up questions
    after the OAuth token is captured — connection type, which drive to
    use, confirmation — via rclone's --non-interactive/--continue
    protocol. Auto-answer with sane defaults so sign-in actually finishes
    instead of leaving a remote with a valid token but no drive_id,
    which fails on every real use ("unable to get drive_id and
    drive_type"). Returns (ok, error_message)."""
    data = response_json
    for _ in range(10):  # hard cap: a protocol change shouldn't spin forever
        state = data.get('State')
        if not state:
            return True, None
        if data.get('Error'):
            return False, data['Error']
        option = data.get('Option') or {}
        answer = _answer_for(option)
        result = subprocess.run(
            ['rclone', 'config', 'update', remote_name, '--non-interactive',
             '--continue', '--state', state, '--result', str(answer)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or 'Configuration step failed'
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, 'Unexpected response from rclone'
    return False, 'Too many configuration steps'


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
            # Only match rclone's actual "go to the following link:" line —
            # an earlier informational line ("Make sure your Redirect URL is
            # set to \"http://...\" in your custom config.") also contains a
            # URL, but it's wrapped in quotes and isn't the real auth link.
            # A naive "first https?:// anywhere" match grabs that one
            # instead, quote and all (as a stray %22), which 404s.
            m = re.search(r'following link:\s*(https?://\S+)', line)
            if m and not url_shown:
                url_shown = True
                if on_url:
                    on_url(m.group(1))
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

    try:
        create_json = json.loads(create.stdout)
    except json.JSONDecodeError:
        create_json = {}
    if create_json.get('State'):
        ok, err = _finish_config_questions(remote_name, create_json)
        if not ok:
            if on_done:
                on_done(False, f'Signed in, but setup didn\'t finish: {err}')
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
