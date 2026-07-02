from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB_PATH = os.path.expanduser('~/.ubuntu-notes/notes.db')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT 'New Note',
            content TEXT DEFAULT '',
            folder TEXT DEFAULT 'Notes',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    for folder in ('Notes', 'Personal', 'Work'):
        conn.execute('INSERT OR IGNORE INTO folders (name) VALUES (?)', (folder,))
    conn.commit()
    conn.close()


def fmt_dt(iso):
    if not iso:
        return ''
    try:
        dt = datetime.fromisoformat(iso)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime('%I:%M %p').lstrip('0')
        if dt.year == now.year:
            return dt.strftime('%b %-d')
        return dt.strftime('%m/%d/%y')
    except Exception:
        return iso


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/notes')
def get_notes():
    folder = request.args.get('folder', 'all')
    conn = get_db()
    if folder == 'all':
        rows = conn.execute(
            "SELECT * FROM notes WHERE folder != 'Trash' ORDER BY updated_at DESC"
        ).fetchall()
    elif folder == 'trash':
        rows = conn.execute(
            "SELECT * FROM notes WHERE folder = 'Trash' ORDER BY updated_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM notes WHERE folder = ? ORDER BY updated_at DESC', (folder,)
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['date_display'] = fmt_dt(d['updated_at'])
        result.append(d)
    return jsonify(result)


@app.route('/api/notes', methods=['POST'])
def create_note():
    data = request.json or {}
    folder = data.get('folder', 'Notes')
    now = datetime.now().isoformat()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO notes (title, content, folder, created_at, updated_at) VALUES (?,?,?,?,?)',
        ('New Note', '', folder, now, now)
    )
    nid = cur.lastrowid
    conn.commit()
    row = dict(conn.execute('SELECT * FROM notes WHERE id=?', (nid,)).fetchone())
    conn.close()
    row['date_display'] = fmt_dt(row['updated_at'])
    return jsonify(row)


@app.route('/api/notes/<int:nid>', methods=['GET'])
def get_note(nid):
    conn = get_db()
    row = conn.execute('SELECT * FROM notes WHERE id=?', (nid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    d = dict(row)
    d['date_display'] = fmt_dt(d['updated_at'])
    return jsonify(d)


@app.route('/api/notes/<int:nid>', methods=['PUT'])
def update_note(nid):
    data = request.json or {}
    content = data.get('content', '')
    lines = [l for l in content.split('\n') if l.strip()]
    title = lines[0].strip()[:120] if lines else 'New Note'
    if not title:
        title = 'New Note'
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        'UPDATE notes SET title=?, content=?, updated_at=? WHERE id=?',
        (title, content, now, nid)
    )
    conn.commit()
    row = dict(conn.execute('SELECT * FROM notes WHERE id=?', (nid,)).fetchone())
    conn.close()
    row['date_display'] = fmt_dt(row['updated_at'])
    return jsonify(row)


@app.route('/api/notes/<int:nid>/move', methods=['PUT'])
def move_note(nid):
    folder = (request.json or {}).get('folder', 'Notes')
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute('UPDATE notes SET folder=?, updated_at=? WHERE id=?', (folder, now, nid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/notes/<int:nid>', methods=['DELETE'])
def delete_note(nid):
    conn = get_db()
    row = conn.execute('SELECT folder FROM notes WHERE id=?', (nid,)).fetchone()
    if row:
        if row['folder'] == 'Trash':
            conn.execute('DELETE FROM notes WHERE id=?', (nid,))
        else:
            conn.execute(
                "UPDATE notes SET folder='Trash', updated_at=? WHERE id=?",
                (datetime.now().isoformat(), nid)
            )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/folders')
def get_folders():
    conn = get_db()
    folders = conn.execute('SELECT * FROM folders ORDER BY name').fetchall()
    result = []
    for f in folders:
        count = conn.execute(
            'SELECT COUNT(*) as c FROM notes WHERE folder=?', (f['name'],)
        ).fetchone()['c']
        result.append({**dict(f), 'count': count})
    all_count = conn.execute(
        "SELECT COUNT(*) as c FROM notes WHERE folder != 'Trash'"
    ).fetchone()['c']
    trash_count = conn.execute(
        "SELECT COUNT(*) as c FROM notes WHERE folder = 'Trash'"
    ).fetchone()['c']
    conn.close()
    return jsonify({'folders': result, 'all_count': all_count, 'trash_count': trash_count})


@app.route('/api/folders', methods=['POST'])
def create_folder():
    name = ((request.json or {}).get('name', '')).strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    conn = get_db()
    try:
        conn.execute('INSERT INTO folders (name) VALUES (?)', (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Folder already exists'}), 409
    conn.close()
    return jsonify({'success': True})


@app.route('/api/folders/<name>', methods=['DELETE'])
def delete_folder(name):
    if name in ('Notes', 'Trash'):
        return jsonify({'error': 'Cannot delete this folder'}), 400
    conn = get_db()
    conn.execute("UPDATE notes SET folder='Notes' WHERE folder=?", (name,))
    conn.execute('DELETE FROM folders WHERE name=?', (name,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notes WHERE (title LIKE ? OR content LIKE ?) AND folder != 'Trash' ORDER BY updated_at DESC",
        (f'%{q}%', f'%{q}%')
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['date_display'] = fmt_dt(d['updated_at'])
        result.append(d)
    return jsonify(result)


if __name__ == '__main__':
    init_db()
    import webbrowser
    print('\n  Ubuntu Notes is running!')
    print('  Open: http://localhost:5001\n')
    webbrowser.open('http://localhost:5001')
    app.run(debug=False, port=5001, host='127.0.0.1')
