"""Background check for a newer release of Nexon Notes on GitHub."""

import json
import threading
import urllib.error
import urllib.request

from PyQt6.QtCore import QObject, pyqtSignal

GITHUB_REPO = 'Aad6552/Nexon-Notes'
REQUEST_TIMEOUT = 5  # seconds


class UpdateSignal(QObject):
    available = pyqtSignal(str)  # emits the newer version string
    up_to_date = pyqtSignal()    # no newer version found
    failed = pyqtSignal()        # network/parsing error


def _version_tuple(version):
    parts = []
    for chunk in version.split('.'):
        digits = ''.join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _fetch_latest_version():
    url = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.load(resp)
    return data.get('tag_name', '').lstrip('v')


def check_for_update_async(current_version, on_available,
                           on_up_to_date=None, on_error=None):
    """Fetches the latest GitHub release in a background thread and calls
    on_available(latest_version) if it's newer than current_version.
    For manual checks, on_up_to_date() fires when already current and
    on_error() on any network/parsing error (offline, rate-limited, no
    releases published yet, etc.); when omitted those outcomes stay silent,
    as befits the automatic background check."""
    def worker():
        try:
            latest = _fetch_latest_version()
        except (urllib.error.URLError, ValueError, OSError):
            if on_error:
                on_error()
            return
        if latest and _version_tuple(latest) > _version_tuple(current_version):
            on_available(latest)
        elif on_up_to_date:
            on_up_to_date()

    threading.Thread(target=worker, daemon=True).start()
