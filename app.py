"""Nexon Notes — web UI + REST API.

Serves the browser frontend (templates/index.html, static/) and a JSON API,
both over the same ~/Notes/notes.db the PyQt6 desktop app (nexon_notes.py)
reads and writes, via the shared notes_db.DB layer. Notes created or edited
here show up in the desktop app and vice versa.

Run: ./run_api.sh   (binds to 127.0.0.1:5001, no auth — localhost only)
"""

from flask import Flask, request, jsonify, render_template, send_from_directory

from notes_db import DB

app = Flask(__name__)
db = DB()


def note_json(row):
    d = dict(row)
    d['date_display'] = DB.fmt_date(d['updated'])
    return d


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory('assets', filename)


@app.route('/api/notes')
def list_notes():
    folder = request.args.get('folder', 'all')
    return jsonify([note_json(r) for r in db.get_notes(folder)])


@app.route('/api/notes', methods=['POST'])
def create_note():
    folder = (request.json or {}).get('folder', 'Notes')
    return jsonify(note_json(db.new_note(folder)))


@app.route('/api/notes/<int:nid>', methods=['GET'])
def get_note(nid):
    row = db.get_note(nid)
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(note_json(row))


@app.route('/api/notes/<int:nid>', methods=['PUT'])
def update_note(nid):
    if not db.get_note(nid):
        return jsonify({'error': 'not found'}), 404
    content = (request.json or {}).get('content', '')
    db.save_note(nid, content)
    return jsonify(note_json(db.get_note(nid)))


@app.route('/api/notes/<int:nid>/move', methods=['PUT'])
def move_note(nid):
    if not db.get_note(nid):
        return jsonify({'error': 'not found'}), 404
    folder = (request.json or {}).get('folder', 'Notes')
    db.move_note(nid, folder)
    return jsonify(note_json(db.get_note(nid)))


@app.route('/api/notes/<int:nid>', methods=['DELETE'])
def delete_note(nid):
    if not db.get_note(nid):
        return jsonify({'error': 'not found'}), 404
    db.del_note(nid)
    return jsonify({'success': True})


@app.route('/api/folders')
def list_folders():
    return jsonify({'folders': db.folders(), 'all_count': db.all_count()})


@app.route('/api/folders', methods=['POST'])
def create_folder():
    name = ((request.json or {}).get('name', '')).strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    if not db.new_folder(name):
        return jsonify({'error': 'Folder already exists'}), 409
    return jsonify({'success': True})


@app.route('/api/folders/<name>', methods=['DELETE'])
def delete_folder(name):
    db.del_folder(name)
    return jsonify({'success': True})


@app.route('/api/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    return jsonify([note_json(r) for r in db.search(q)])


if __name__ == '__main__':
    print('\n  Nexon Notes API running at http://127.0.0.1:5001')
    print('  Reading/writing the same database as the desktop app: ~/Notes/notes.db\n')
    app.run(debug=False, port=5001, host='127.0.0.1')
