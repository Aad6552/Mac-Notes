"""One-time import from the macOS Notes app.

Runs an AppleScript against Notes.app (via osascript) that emits
"<folder path><US><plaintext><RS>" records. macOS will prompt for Automation
permission ("Nexon Notes wants to control Notes") the first time this runs.

Walks folders and asks for `plaintext of (every note of f)` in one batched
Apple Event per folder, rather than one event per note — fetching each
note's plaintext individually (e.g. via `every note` + a per-note repeat
loop) is 50-100x slower since each property access on a note is its own
round trip; batching by folder cut a 1,100-note library from minutes down
to about 10 seconds in testing.

Notes.app folders can be nested (and different accounts can each have a
folder with the same name, e.g. a "Completed" sub-folder under several
different parents), but Nexon Notes' own folder model is flat. So each
folder's full ancestry (up to but not including the account, e.g.
"TD Synnex Inc. › AI Apps › Maximo") is joined into a single
path string and used as the flat folder name — this both preserves the
hierarchy visually and keeps same-named folders under different parents
from colliding into one.

The unit/record separators are NUL-delimited (not bare 0x1E/0x1F) on
purpose: a plain ASCII 0x1E/0x1F collided for real on a note containing a
pasted spreadsheet table that happened to embed those exact control bytes,
truncating that note and spilling its tail into a phantom folder. A NUL
byte can't survive inside a Notes.app rich-text body at all, so wrapping
the separators in NULs makes the delimiters collision-proof.
"""

import re
import subprocess

UNIT_SEP = '\x00\x01\x00'
RECORD_SEP = '\x00\x02\x00'
PATH_SEP = ' › '  # visual "parent › child" join for flattened folder paths
IMPORT_TIMEOUT = 120  # seconds

_SCRIPT = f'''
on folderPath(f)
    tell application "Notes"
        set p to name of f
        set c to container of f
        repeat while ((class of c) as string) is "folder"
            set p to (name of c) & "{PATH_SEP}" & p
            set c to container of c
        end repeat
        return p
    end tell
end folderPath

tell application "Notes"
    set us to (ASCII character 0) & (ASCII character 1) & (ASCII character 0)
    set rs to (ASCII character 0) & (ASCII character 2) & (ASCII character 0)
    set out to ""
    repeat with f in (every folder)
        set fpath to my folderPath(f)
        set bodies to plaintext of (every note of f)
        repeat with b in bodies
            set out to out & fpath & us & b & rs
        end repeat
    end repeat
    return out
end tell
'''


class AppleNotesImportError(Exception):
    pass


def fetch_notes():
    """Blocking — call from a background thread. Returns a list of
    {'folder': str, 'content': str} dicts, one per note in Notes.app.
    Raises AppleNotesImportError on failure (Notes not installed/running,
    Automation permission denied, timeout, etc)."""
    try:
        result = subprocess.run(
            ['osascript', '-e', _SCRIPT],
            capture_output=True, text=True, timeout=IMPORT_TIMEOUT,
        )
    except FileNotFoundError:
        raise AppleNotesImportError('osascript is not available (macOS only)')
    except subprocess.TimeoutExpired:
        raise AppleNotesImportError('Timed out reading notes from the Notes app')

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if 'Not authorized' in stderr or '-1743' in stderr:
            raise AppleNotesImportError(
                'Nexon Notes isn\'t authorized to control Notes — grant access '
                'in System Settings → Privacy & Security → Automation, '
                'then try again.'
            )
        raise AppleNotesImportError(stderr or 'Could not read notes from the Notes app')

    records = result.stdout.split(RECORD_SEP)
    notes = []
    for record in records:
        if not record:
            continue
        folder, _, content = record.partition(UNIT_SEP)
        # sqlite3 rejects NUL characters in text params outright (raises
        # ValueError); rich-content notes can carry stray control chars.
        content = content.replace('\x00', '')
        notes.append({'folder': folder.strip() or 'Notes', 'content': content})
    return notes


def safe_folder_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '-', name).strip(' .')
    return name[:120] or 'Imported'
