"""Shared SQLite storage for Nexon Notes.

Used by both the PyQt6 desktop app (nexon_notes.py) and the REST API
(app.py) so they read and write the same ~/Notes/notes.db, with no Qt
dependency here.
"""

import os
import sqlite3
from datetime import datetime

NOTES_DIR = os.path.expanduser('~/Notes')
DB_PATH = os.path.join(NOTES_DIR, 'notes.db')


class DB:
    def __init__(self):
        os.makedirs(NOTES_DIR, exist_ok=True)
        self.con = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS folders (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                ts   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS notes (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                title   TEXT DEFAULT 'New Note',
                content TEXT DEFAULT '',
                folder  TEXT DEFAULT 'Notes',
                created TEXT DEFAULT (datetime('now')),
                updated TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Seed defaults only the very first time this DB is ever opened, tracked
        # via meta.seeded — not by checking if folders is currently empty, since
        # deleting all folders would otherwise make them reappear on next launch.
        seeded = self.con.execute("SELECT value FROM meta WHERE key='seeded'").fetchone()
        if not seeded:
            for f in ('Notes', 'Personal', 'Work'):
                self.con.execute('INSERT OR IGNORE INTO folders (name) VALUES (?)', (f,))
            self.con.execute("INSERT INTO meta (key, value) VALUES ('seeded', '1')")
        self._migrate()
        self.con.commit()

    def _migrate(self):
        # Tags notes created by "Import from Apple Notes" so a later Wipe &
        # Re-import can remove exactly those (and only those) without
        # touching notes typed by hand in Nexon Notes.
        cols = {r['name'] for r in self.con.execute('PRAGMA table_info(notes)')}
        if 'from_apple_import' not in cols:
            self.con.execute(
                'ALTER TABLE notes ADD COLUMN from_apple_import INTEGER DEFAULT 0'
            )

    def folders(self):
        rows = self.con.execute('SELECT name FROM folders ORDER BY name').fetchall()
        out = []
        for r in rows:
            n = r['name']
            c = self.con.execute(
                'SELECT COUNT(*) c FROM notes WHERE folder=?', (n,)
            ).fetchone()['c']
            out.append({'name': n, 'count': c})
        return out

    def all_count(self):
        return self.con.execute('SELECT COUNT(*) c FROM notes').fetchone()['c']

    def get_notes(self, folder):
        if folder == 'all':
            return self.con.execute(
                'SELECT * FROM notes ORDER BY updated DESC'
            ).fetchall()
        return self.con.execute(
            'SELECT * FROM notes WHERE folder=? ORDER BY updated DESC', (folder,)
        ).fetchall()

    def get_note(self, nid):
        return self.con.execute('SELECT * FROM notes WHERE id=?', (nid,)).fetchone()

    def new_note(self, folder='Notes'):
        now = datetime.now().isoformat()
        cur = self.con.execute(
            'INSERT INTO notes (title,content,folder,created,updated) VALUES (?,?,?,?,?)',
            ('New Note', '', folder, now, now)
        )
        self.con.commit()
        return dict(self.get_note(cur.lastrowid))

    def save_note(self, nid, content):
        lines = [l for l in content.split('\n') if l.strip()]
        title = (lines[0][:120] if lines else '') or 'New Note'
        self.con.execute(
            'UPDATE notes SET title=?,content=?,updated=? WHERE id=?',
            (title, content, datetime.now().isoformat(), nid)
        )
        self.con.commit()

    def new_folder(self, name):
        try:
            self.con.execute('INSERT INTO folders (name) VALUES (?)', (name,))
            self.con.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # duplicate name

    def del_note(self, nid):
        self.con.execute('DELETE FROM notes WHERE id=?', (nid,))
        self.con.commit()

    def del_folder(self, name):
        self.con.execute('DELETE FROM notes WHERE folder=?', (name,))
        self.con.execute('DELETE FROM folders WHERE name=?', (name,))
        self.con.commit()

    def move_note(self, nid, folder):
        self.con.execute(
            'UPDATE notes SET folder=?,updated=? WHERE id=?',
            (folder, datetime.now().isoformat(), nid)
        )
        self.con.commit()

    def imported_folder_content_pairs(self):
        """(folder, content) for every existing note, used by a Merge import
        to recognize a note it already has and skip re-adding it."""
        return {(r['folder'], r['content'])
                for r in self.con.execute('SELECT folder, content FROM notes')}

    def import_apple_note(self, folder, content):
        lines = [l for l in content.split('\n') if l.strip()]
        title = (lines[0][:120] if lines else '') or 'New Note'
        now = datetime.now().isoformat()
        self.con.execute(
            'INSERT INTO notes (title,content,folder,created,updated,from_apple_import) '
            'VALUES (?,?,?,?,?,1)',
            (title, content, folder, now, now)
        )
        self.con.commit()

    def delete_apple_imported_notes(self):
        """Wipe & Re-import: remove everything a previous Apple Notes import
        created, leaving hand-typed notes untouched."""
        self.con.execute('DELETE FROM notes WHERE from_apple_import=1')
        self.con.commit()

    def prune_empty_folders(self, keep=('Notes', 'Personal', 'Work')):
        used = {r['folder'] for r in self.con.execute('SELECT DISTINCT folder FROM notes')}
        for r in self.con.execute('SELECT name FROM folders').fetchall():
            if r['name'] not in used and r['name'] not in keep:
                self.con.execute('DELETE FROM folders WHERE name=?', (r['name'],))
        self.con.commit()

    def search(self, q):
        return self.con.execute(
            'SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY updated DESC',
            (f'%{q}%', f'%{q}%')
        ).fetchall()

    @staticmethod
    def fmt_date(iso):
        if not iso:
            return ''
        try:
            dt = datetime.fromisoformat(iso)
            n = datetime.now()
            if dt.date() == n.date():
                return dt.strftime('%-I:%M %p')
            if dt.year == n.year:
                return dt.strftime('%b %-d')
            return dt.strftime('%-m/%-d/%y')
        except Exception:
            return ''
