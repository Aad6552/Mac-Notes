/* Mac Notes — Frontend */
(() => {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────────────
  let state = {
    currentFolder: 'all',
    currentNoteId: null,
    notes: [],
    folders: [],
    saveTimer: null,
    searchMode: false,
    contextNoteId: null,
    allCount: 0,
  };

  // ── Elements ───────────────────────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const el = {
    folderList:      $('folder-list'),
    notesList:       $('notes-list'),
    panelTitle:      $('panel-title'),
    panelCount:      $('panel-count'),
    countAll:        $('count-all'),
    searchInput:     $('search-input'),
    btnNewNote:      $('btn-new-note'),
    btnNewFolder:    $('btn-new-folder'),
    editorToolbar:   $('editor-toolbar'),
    editorContent:   $('editor-content'),
    editorPlaceholder: $('editor-placeholder'),
    editorWrap:      $('editor-wrap'),
    editorNoteInfo:  $('editor-note-info'),
    editorDate:      $('editor-date'),
    editorFolderSel: $('editor-folder-select'),
    btnDeleteNote:   $('btn-delete-note'),
    sortSelect:      $('sort-select'),
    modalNewFolder:  $('modal-new-folder'),
    newFolderName:   $('new-folder-name'),
    modalCancel:     $('modal-cancel'),
    modalConfirm:    $('modal-confirm'),
    contextMenu:     $('context-menu'),
    ctxMove:         $('ctx-move'),
    ctxDelete:       $('ctx-delete'),
  };

  // ── API helpers ────────────────────────────────────────────────────────────
  const api = {
    async get(path) {
      const r = await fetch(path);
      return r.json();
    },
    async post(path, body) {
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      return r.json();
    },
    async put(path, body) {
      const r = await fetch(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      return r.json();
    },
    async del(path) {
      const r = await fetch(path, { method: 'DELETE' });
      return r.json();
    },
  };

  // ── Folder rendering ───────────────────────────────────────────────────────
  async function loadFolders() {
    const data = await api.get('/api/folders');
    state.folders = data.folders;
    state.allCount = data.all_count;

    el.countAll.textContent = data.all_count || '';

    // Re-render dynamic folders (between header and divider)
    const existing = el.folderList.querySelectorAll('.dynamic-folder');
    existing.forEach(e => e.remove());

    // Insert after the sidebar-section-title (which is not in the folderList)
    // Actually sidebar-section-title is outside folderList... let me insert before divider
    const divider = el.folderList.querySelector('.sidebar-divider');

    state.folders.forEach(f => {
      const item = document.createElement('div');
      item.className = 'folder-item dynamic-folder';
      item.dataset.folder = f.name;
      if (f.name === state.currentFolder) item.classList.add('active');
      item.innerHTML = `
        <span class="folder-icon">📁</span>
        <span class="folder-name">${escHtml(f.name)}</span>
        <span class="folder-count">${f.count || ''}</span>
      `;
      item.addEventListener('click', () => selectFolder(f.name));
      item.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        if (!['Notes'].includes(f.name)) showFolderContextMenu(e, f.name);
      });
      el.folderList.insertBefore(item, divider);
    });

    // Update folder select in editor
    rebuildFolderSelect();
  }

  function rebuildFolderSelect() {
    el.editorFolderSel.innerHTML = '';
    state.folders.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.name;
      opt.textContent = f.name;
      el.editorFolderSel.appendChild(opt);
    });
    if (state.currentNoteId) {
      const note = state.notes.find(n => n.id === state.currentNoteId);
      if (note) el.editorFolderSel.value = note.folder;
    }
  }

  // ── Note list rendering ────────────────────────────────────────────────────
  async function loadNotes(folder) {
    let notes;
    if (state.searchMode) {
      notes = await api.get(`/api/search?q=${encodeURIComponent(el.searchInput.value)}`);
    } else {
      notes = await api.get(`/api/notes?folder=${encodeURIComponent(folder)}`);
    }

    // Sort
    const sort = el.sortSelect.value;
    if (sort === 'title') {
      notes.sort((a, b) => a.title.localeCompare(b.title));
    } else if (sort === 'created') {
      notes.sort((a, b) => (b.created || '').localeCompare(a.created || ''));
    }

    state.notes = notes;
    renderNotesList();
    await loadFolders();
  }

  function renderNotesList() {
    const notes = state.notes;
    el.panelCount.textContent = notes.length ? `${notes.length} note${notes.length !== 1 ? 's' : ''}` : '';

    if (!notes.length) {
      el.notesList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📝</div>
          <div class="empty-state-text">${state.searchMode ? 'No results found.' : 'No notes yet.<br>Click + to create one.'}</div>
        </div>`;
      return;
    }

    const showFolderBadge = state.currentFolder === 'all' || state.searchMode;

    el.notesList.innerHTML = notes.map(n => {
      const preview = getPreview(n.content);
      const active = n.id === state.currentNoteId ? ' active' : '';
      const badge = showFolderBadge && n.folder !== 'Notes'
        ? `<span class="note-item-folder-badge">${escHtml(n.folder)}</span>` : '';
      return `
        <div class="note-item${active}" data-id="${n.id}">
          <div class="note-item-title">${escHtml(n.title || 'New Note')}</div>
          <div class="note-item-meta">
            <span class="note-item-date">${escHtml(n.date_display || '')}</span>
            ${badge}
          </div>
          <div class="note-item-preview">${escHtml(preview)}</div>
        </div>`;
    }).join('');

    el.notesList.querySelectorAll('.note-item').forEach(item => {
      item.addEventListener('click', () => openNote(parseInt(item.dataset.id)));
      item.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showNoteContextMenu(e, parseInt(item.dataset.id));
      });
    });
  }

  function getPreview(content) {
    if (!content) return 'No additional text';
    const lines = content.split('\n').filter(l => l.trim());
    const body = lines.slice(1).join(' ').trim();
    return body ? body.slice(0, 80) : 'No additional text';
  }

  // ── Folder selection ───────────────────────────────────────────────────────
  function selectFolder(folder) {
    state.currentFolder = folder;
    state.searchMode = false;
    el.searchInput.value = '';

    // Update active state
    el.folderList.querySelectorAll('.folder-item').forEach(item => {
      item.classList.toggle('active', item.dataset.folder === folder);
    });

    el.panelTitle.textContent = folder === 'all' ? 'All Notes' : folder;

    // Close editor if current note not in this folder
    if (state.currentNoteId) {
      const note = state.notes.find(n => n.id === state.currentNoteId);
      if (note && folder !== 'all' && note.folder !== folder) {
        closeEditor();
      }
    }

    loadNotes(folder);
  }

  // ── Wire sidebar folder items ──────────────────────────────────────────────
  el.folderList.querySelectorAll('.folder-item[data-folder]').forEach(item => {
    item.addEventListener('click', () => selectFolder(item.dataset.folder));
  });

  // ── Note opening ───────────────────────────────────────────────────────────
  async function openNote(id) {
    if (state.currentNoteId === id) return;

    // Save previous note first
    if (state.currentNoteId) await flushSave();

    state.currentNoteId = id;
    const data = await api.get(`/api/notes/${id}`);

    el.editorContent.innerHTML = contentToHtml(data.content || '');
    el.editorContent.contentEditable = 'true';
    el.editorContent.style.display = 'block';
    el.editorPlaceholder.style.display = 'none';
    el.editorToolbar.classList.remove('hidden');
    el.editorNoteInfo.style.display = 'flex';
    el.editorDate.textContent = data.date_display || '';
    el.editorFolderSel.value = data.folder;

    renderNotesList();
    el.editorContent.focus();

    // Put cursor at end
    const range = document.createRange();
    range.selectNodeContents(el.editorContent);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function closeEditor() {
    state.currentNoteId = null;
    el.editorContent.contentEditable = 'false';
    el.editorContent.style.display = 'none';
    el.editorPlaceholder.style.display = 'flex';
    el.editorToolbar.classList.add('hidden');
    el.editorNoteInfo.style.display = 'none';
  }

  // Simple HTML ↔ text conversion (preserve line breaks)
  function contentToHtml(text) {
    return text
      .split('\n')
      .map((line, i) => {
        const escaped = escHtml(line);
        if (i === 0) return `<div class="note-title-line">${escaped || '<br>'}</div>`;
        return `<div>${escaped || '<br>'}</div>`;
      })
      .join('');
  }

  function htmlToContent(html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    const lines = [];
    div.childNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) {
        lines.push(node.textContent);
      } else {
        lines.push(node.textContent || '');
      }
    });
    return lines.join('\n').replace(/\n{3,}/g, '\n\n');
  }

  // ── Auto-save ──────────────────────────────────────────────────────────────
  el.editorContent.addEventListener('input', () => {
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(saveCurrentNote, 800);
    updateToolbarState();
  });

  async function saveCurrentNote() {
    if (!state.currentNoteId) return;
    const content = htmlToContent(el.editorContent.innerHTML);
    const updated = await api.put(`/api/notes/${state.currentNoteId}`, { content });
    el.editorDate.textContent = updated.date_display || '';

    // Update list item without full reload
    const noteIndex = state.notes.findIndex(n => n.id === state.currentNoteId);
    if (noteIndex >= 0) {
      state.notes[noteIndex] = { ...state.notes[noteIndex], ...updated };
      // Move to top since it was just edited (if sorted by date)
      if (el.sortSelect.value === 'updated') {
        const [note] = state.notes.splice(noteIndex, 1);
        state.notes.unshift(note);
      }
      renderNotesList();
    }
    await loadFolders();
  }

  async function flushSave() {
    clearTimeout(state.saveTimer);
    await saveCurrentNote();
  }

  // ── New note ───────────────────────────────────────────────────────────────
  el.btnNewNote.addEventListener('click', async () => {
    await flushSave();
    const folder = state.currentFolder === 'all' ? 'Notes' : state.currentFolder;
    const note = await api.post('/api/notes', { folder });
    state.notes.unshift({ ...note, date_display: 'Now' });
    renderNotesList();
    await openNote(note.id);
    await loadFolders();
  });

  // ── Delete note ────────────────────────────────────────────────────────────
  el.btnDeleteNote.addEventListener('click', () => deleteNote(state.currentNoteId));

  async function deleteNote(id) {
    if (!id) return;
    if (!confirm('Permanently delete this note?')) return;
    await api.del(`/api/notes/${id}`);
    if (state.currentNoteId === id) closeEditor();
    state.notes = state.notes.filter(n => n.id !== id);
    renderNotesList();
    await loadFolders();
  }

  // ── Move note folder ───────────────────────────────────────────────────────
  el.editorFolderSel.addEventListener('change', async () => {
    if (!state.currentNoteId) return;
    const folder = el.editorFolderSel.value;
    await api.put(`/api/notes/${state.currentNoteId}/move`, { folder });
    const note = state.notes.find(n => n.id === state.currentNoteId);
    if (note) note.folder = folder;
    await loadFolders();
    // If we're in a specific folder view that doesn't match, remove from list
    if (!['all'].includes(state.currentFolder) && state.currentFolder !== folder) {
      state.notes = state.notes.filter(n => n.id !== state.currentNoteId);
      closeEditor();
      renderNotesList();
    }
  });

  // ── Toolbar formatting ─────────────────────────────────────────────────────
  el.editorToolbar.querySelectorAll('.toolbar-btn[data-cmd]').forEach(btn => {
    btn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      const cmd = btn.dataset.cmd;
      if (cmd.startsWith('formatBlock-')) {
        document.execCommand('formatBlock', false, cmd.split('-')[1]);
      } else {
        document.execCommand(cmd, false, null);
      }
      el.editorContent.focus();
      updateToolbarState();
    });
  });

  function updateToolbarState() {
    ['bold', 'italic', 'underline', 'strikeThrough', 'insertUnorderedList', 'insertOrderedList'].forEach(cmd => {
      const btn = el.editorToolbar.querySelector(`[data-cmd="${cmd}"]`);
      if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
    });
  }

  el.editorContent.addEventListener('keyup', updateToolbarState);
  el.editorContent.addEventListener('mouseup', updateToolbarState);

  // Keyboard shortcuts
  el.editorContent.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      if (e.key === 's') { e.preventDefault(); flushSave(); }
    }
    // Tab inserts spaces
    if (e.key === 'Tab') {
      e.preventDefault();
      document.execCommand('insertText', false, '    ');
    }
  });

  // ── Search ─────────────────────────────────────────────────────────────────
  let searchTimer;
  el.searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = el.searchInput.value.trim();
    if (!q) {
      state.searchMode = false;
      el.panelTitle.textContent = labelForFolder(state.currentFolder);
      loadNotes(state.currentFolder);
      return;
    }
    searchTimer = setTimeout(async () => {
      state.searchMode = true;
      el.panelTitle.textContent = `Search: "${q}"`;
      const results = await api.get(`/api/search?q=${encodeURIComponent(q)}`);
      state.notes = results;
      renderNotesList();
    }, 250);
  });

  el.searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      el.searchInput.value = '';
      state.searchMode = false;
      el.panelTitle.textContent = labelForFolder(state.currentFolder);
      loadNotes(state.currentFolder);
    }
  });

  function labelForFolder(folder) {
    return folder === 'all' ? 'All Notes' : folder;
  }

  // ── Sort ───────────────────────────────────────────────────────────────────
  el.sortSelect.addEventListener('change', () => loadNotes(state.currentFolder));

  // ── New folder modal ───────────────────────────────────────────────────────
  el.btnNewFolder.addEventListener('click', () => {
    el.modalNewFolder.classList.remove('hidden');
    el.newFolderName.value = '';
    el.newFolderName.focus();
  });

  el.modalCancel.addEventListener('click', () => el.modalNewFolder.classList.add('hidden'));

  el.modalConfirm.addEventListener('click', async () => {
    const name = el.newFolderName.value.trim();
    if (!name) return;
    await api.post('/api/folders', { name });
    el.modalNewFolder.classList.add('hidden');
    await loadFolders();
  });

  el.newFolderName.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') el.modalConfirm.click();
    if (e.key === 'Escape') el.modalCancel.click();
  });

  el.modalNewFolder.addEventListener('click', (e) => {
    if (e.target === el.modalNewFolder) el.modalCancel.click();
  });

  // ── Context menu ───────────────────────────────────────────────────────────
  function showNoteContextMenu(e, id) {
    state.contextNoteId = id;
    const menu = el.contextMenu;
    menu.classList.remove('hidden');
    menu.style.left = `${Math.min(e.clientX, window.innerWidth - 180)}px`;
    menu.style.top = `${Math.min(e.clientY, window.innerHeight - 100)}px`;
  }

  el.ctxDelete.addEventListener('click', async () => {
    if (state.contextNoteId) await deleteNote(state.contextNoteId);
    el.contextMenu.classList.add('hidden');
  });

  el.ctxMove.addEventListener('click', () => {
    el.contextMenu.classList.add('hidden');
    if (!state.contextNoteId) return;
    const available = state.folders.map(f => f.name);
    const folder = prompt(`Move to folder:\n${available.join(', ')}`);
    if (folder && available.includes(folder)) {
      api.put(`/api/notes/${state.contextNoteId}/move`, { folder }).then(() => {
        loadNotes(state.currentFolder);
        loadFolders();
        if (state.currentNoteId === state.contextNoteId) {
          el.editorFolderSel.value = folder;
        }
      });
    }
  });

  document.addEventListener('click', (e) => {
    if (!el.contextMenu.contains(e.target)) el.contextMenu.classList.add('hidden');
  });

  function showFolderContextMenu(e, folderName) {
    // Simple: confirm delete
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    menu.innerHTML = `<div class="ctx-item danger" id="ctx-del-folder">🗑 Delete Folder</div>`;
    document.body.appendChild(menu);
    menu.querySelector('#ctx-del-folder').addEventListener('click', async () => {
      if (confirm(`Delete folder "${folderName}"? Notes will move to Notes.`)) {
        await api.del(`/api/folders/${encodeURIComponent(folderName)}`);
        if (state.currentFolder === folderName) selectFolder('all');
        await loadFolders();
        await loadNotes(state.currentFolder);
      }
      menu.remove();
    });
    const dismiss = (ev) => { if (!menu.contains(ev.target)) { menu.remove(); document.removeEventListener('click', dismiss); } };
    setTimeout(() => document.addEventListener('click', dismiss), 0);
  }

  // ── Escape key ─────────────────────────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      el.contextMenu.classList.add('hidden');
      el.modalNewFolder.classList.add('hidden');
    }
  });

  // ── Utilities ──────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  async function init() {
    await loadFolders();
    await loadNotes('all');
  }

  init();
})();
