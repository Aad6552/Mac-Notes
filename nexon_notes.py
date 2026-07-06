#!/usr/bin/env python3
"""Nexon Notes — Native desktop app (PyQt6)"""

import sys
import os
import fcntl
import subprocess
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QListWidget,
    QListWidgetItem, QTextEdit, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFrame, QMessageBox, QMenu, QStackedWidget,
    QColorDialog, QSpinBox, QInputDialog,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPixmap, QPainter, QPen, QCursor,
    QTextCharFormat, QTextCursor, QAction, QKeySequence,
)

from cloud_sync import CloudSync
from cloud_accounts_dialog import CloudAccountsDialog
from notes_db import DB, NOTES_DIR, DB_PATH
from update_check import UpdateSignal, check_for_update_async
from apple_notes_import import fetch_notes, safe_folder_name, AppleNotesImportError

# ── Paths ─────────────────────────────────────────────────────────────────────
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'assets', 'logo.png')
VERSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VERSION')
GET_LATEST_RELEASE_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'bin', 'get-latest-release.sh')

try:
    with open(VERSION_PATH) as f:
        APP_VERSION = f.read().strip()
except OSError:
    APP_VERSION = ''

# ── Colours ───────────────────────────────────────────────────────────────────
ORANGE    = '#E95420'
DARK_BG   = '#2C2427'
DARK_BG2  = '#211C1F'
DARK_FG   = '#E8E0E3'
LIST_BG   = '#F5F5F5'
EDITOR_BG = '#FFFEF5'

STYLE = f"""
QMainWindow, QWidget#root {{ background: {DARK_BG2}; }}

/* ── Sidebar ── */
QWidget#sidebar {{
    background: {DARK_BG};
    border-right: 1px solid #180F14;
}}
QLabel#brand-name {{
    color: white;
    font-size: 15px;
    font-weight: bold;
}}
QLabel#brand-version {{
    color: #9A8A8F;
    font-size: 10px;
}}
QLabel#section-label {{
    color: #5A4A4F;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 8px 16px 2px;
}}
QListWidget#folder-list {{
    background: transparent;
    border: none;
    outline: none;
    padding: 4px 0;
}}
QListWidget#folder-list::item {{
    border-radius: 8px;
    color: {DARK_FG};
    font-size: 13px;
    margin: 1px 8px;
    padding: 5px 8px;
}}
QListWidget#folder-list::item:hover  {{ background: #3D3438; }}
QListWidget#folder-list::item:selected {{ background: #4A3C40; color: white; }}

QLabel#cloud-status-label {{
    color: #B5A8AC;
    font-size: 11px;
    padding: 2px 14px 0;
}}
QPushButton#cloud-accounts-btn {{
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px;
    color: {DARK_FG};
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    margin: 8px 10px 12px;
    padding: 8px 10px;
}}
QPushButton#cloud-accounts-btn:hover {{
    background: rgba(255,255,255,0.15);
    border-color: rgba(255,255,255,0.25);
}}
QPushButton#cloud-accounts-btn:pressed {{ background: rgba(255,255,255,0.20); }}

/* ── Search ── */
QLineEdit#search-entry {{
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 8px;
    color: white;
    font-size: 13px;
    padding: 5px 10px;
    margin: 8px 10px 6px;
}}
QLineEdit#search-entry:focus {{
    background: rgba(255,255,255,0.16);
    border-color: rgba(255,255,255,0.22);
}}

/* ── Notes panel ── */
QWidget#notes-panel {{
    background: {LIST_BG};
    border-right: 1px solid #DCDCDC;
}}
QLabel#panel-title {{
    color: #1A1A1A;
    font-size: 15px;
    font-weight: 600;
    padding: 10px 14px 8px;
}}
QListWidget#notes-list {{
    background: {LIST_BG};
    border: none;
    outline: none;
}}
QListWidget#notes-list::item {{
    border-bottom: 1px solid #E2E2E2;
    border-left: 3px solid transparent;
    padding: 0;
}}
QListWidget#notes-list::item:hover   {{ background: #EBEBEB; }}
QListWidget#notes-list::item:selected {{
    background: white;
    border-left: 3px solid {ORANGE};
}}
QPushButton#new-note-btn {{
    background: #1A1A1A;
    border: none;
    border-radius: 10px;
    color: white;
    font-size: 14px;
    font-weight: bold;
    margin: 0 10px 8px 10px;
    min-height: 40px; max-height: 40px;
    padding-bottom: 1px;
}}
QPushButton#new-note-btn:hover   {{ background: #333333; }}
QPushButton#new-note-btn:pressed {{ background: #000000; }}

/* ── Editor ── */
QWidget#editor-panel   {{ background: {EDITOR_BG}; }}
QWidget#editor-toolbar {{
    background: white;
    border-bottom: 1px solid #E8E8E8;
    padding: 3px 8px;
}}
QLabel#folder-info-label {{ color: #BBBBBB; font-size: 11px; padding: 0 8px; }}
QTextEdit#note-editor {{
    background: {EDITOR_BG};
    border: none;
    color: #1A1A1A;
    font-family: "Helvetica Neue", Helvetica, sans-serif;
    font-size: 14pt;
    padding: 0;
    selection-background-color: #FBD0C0;
    selection-color: #1A1A1A;
}}

/* ── Placeholder ── */
QLabel#ph-icon  {{ color: #CCCCCC; font-size: 54px; }}
QLabel#ph-title {{ color: #BBBBBB; font-size: 22px; font-weight: 300; }}
QLabel#ph-sub   {{ color: #CCCCCC; font-size: 11px; }}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: transparent; width: 7px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(0,0,0,0.14); border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

/* ── Splitter ── */
QSplitter::handle {{ background: transparent; width: 1px; }}

/* ── Menus ── */
QMenu {{
    background: white;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    color: #1A1A1A;
    padding: 6px 16px;
    border-radius: 4px;
    font-size: 13px;
}}
QMenu::item:selected {{ background: #F5F5F5; }}
QMenu::item.danger   {{ color: #CC3333; }}
"""


# ── Cross-thread signal for cloud sync results ────────────────────────────────
class SyncSignal(QObject):
    finished = pyqtSignal()


# ── Cross-thread signal for Apple Notes import results ────────────────────────
class ImportSignal(QObject):
    done = pyqtSignal(int, int, str)  # imported count, skipped count, error ('' on success)


# ── Note list row widget ──────────────────────────────────────────────────────
class NoteRow(QWidget):
    def __init__(self, note, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 9)
        lay.setSpacing(2)

        self._title = QLabel(note['title'] or 'New Note')
        tf = QFont(); tf.setPointSize(10); tf.setBold(True)
        self._title.setFont(tf)
        self._title.setStyleSheet('color: #1A1A1A;')

        date_lbl = QLabel(DB.fmt_date(note['updated']))
        df = QFont(); df.setPointSize(8)
        date_lbl.setFont(df)
        date_lbl.setStyleSheet('color: #999999;')

        body = [l.strip() for l in (note['content'] or '').split('\n') if l.strip()][1:]
        prev = QLabel(' '.join(body)[:80] or 'No additional text')
        pf = QFont(); pf.setPointSize(9)
        prev.setFont(pf)
        prev.setStyleSheet('color: #AAAAAA;')

        lay.addWidget(self._title)
        lay.addWidget(date_lbl)
        lay.addWidget(prev)

    def set_selected(self, on):
        self._title.setStyleSheet(f'color: {ORANGE};' if on else 'color: #1A1A1A;')


# ── Lined-paper text editor ───────────────────────────────────────────────────
class PaperEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('note-editor')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.document().setDocumentMargin(52)
        self.setContentsMargins(0, 36, 0, 36)

    def paintEvent(self, event):
        p = QPainter(self.viewport())
        p.setPen(QPen(QColor(200, 192, 165, 55), 0.6))
        lh = self.fontMetrics().height() + 6
        y  = 36 + 52
        while y < self.viewport().height() + lh:
            p.drawLine(32, y, self.viewport().width() - 32, y)
            y += lh
        p.end()
        super().paintEvent(event)


# ── Main window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, db: DB):
        super().__init__()
        self.db = db
        self.current_folder = 'all'
        self.current_note_id = None
        self._busy = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

        # Cloud backup: pushes notes.db to Proton Drive / OneDrive /
        # Google Drive / Dropbox via rclone, whichever the user is signed in to.
        self.cloud = CloudSync(DB_PATH)
        self._sync_signal = SyncSignal()
        self._sync_signal.finished.connect(self._on_cloud_sync_done)

        self._import_signal = ImportSignal()
        self._import_signal.done.connect(self._on_apple_notes_import_done)

        self._cloud_debounce_timer = QTimer(self)  # fires a bit after typing settles
        self._cloud_debounce_timer.setSingleShot(True)
        self._cloud_debounce_timer.timeout.connect(self._trigger_cloud_sync)

        # Also keep syncing continuously in the background; sync_all_async()
        # no-ops (via its lock) if a previous pass is still in flight, so this
        # just means "sync again as soon as possible" rather than overlapping runs.
        self._cloud_periodic_timer = QTimer(self)
        self._cloud_periodic_timer.setInterval(2000)
        self._cloud_periodic_timer.timeout.connect(self._trigger_cloud_sync)
        self._cloud_periodic_timer.start()

        QTimer.singleShot(5000, self._trigger_cloud_sync)  # + once shortly after launch

        self._update_signal = UpdateSignal()
        self._update_signal.available.connect(self._on_update_available)
        self._update_signal.up_to_date.connect(self._on_update_up_to_date)
        self._update_signal.failed.connect(self._on_update_check_failed)
        QTimer.singleShot(4000, self._check_for_updates)

        self.setWindowTitle(f'Nexon Notes v{APP_VERSION}' if APP_VERSION else 'Nexon Notes')
        self.resize(1160, 760)

        logo_pix = QPixmap(LOGO_PATH)
        if not logo_pix.isNull():
            self.setWindowIcon(QIcon(logo_pix))

        self._build_ui()
        self._reload_all()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget(); root.setObjectName('root')
        self.setCentralWidget(root)
        rl = QHBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        spl = QSplitter(Qt.Orientation.Horizontal)
        spl.setHandleWidth(1)
        spl.setStyleSheet('QSplitter::handle { background: #1a0f14; }')
        rl.addWidget(spl)

        spl.addWidget(self._mk_sidebar())
        spl.addWidget(self._mk_notes_panel())
        spl.addWidget(self._mk_editor())
        spl.setSizes([220, 285, 655])
        spl.setCollapsible(0, False)
        spl.setCollapsible(1, False)

        self._build_menus()

    # ── Menu bar ──────────────────────────────────────────────────────────────
    def _build_menus(self):
        mb = self.menuBar()
        is_linux = sys.platform.startswith('linux')
        if is_linux:
            # Some Linux shells (Ubuntu/Unity's global "app menu" export) render
            # exported QMenuBar items greyed-out/unresponsive for plain Python
            # apps. Keeping the menu bar in-window avoids that entirely.
            mb.setNativeMenuBar(False)

        def act(menu, text, slot, shortcut=None, role=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if role is not None:
                a.setMenuRole(role)
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        file_menu = mb.addMenu('&File')
        act(file_menu, 'New Note', self._on_new_note, 'Ctrl+N')
        act(file_menu, 'New Folder…', self._on_new_folder, 'Ctrl+Shift+N')
        act(file_menu, 'Save', self._flush, 'Ctrl+S')
        file_menu.addSeparator()
        act(file_menu, 'Sync to Cloud Now', self._trigger_cloud_sync, 'Ctrl+Shift+S')
        act(file_menu, 'Cloud Accounts…', self._open_cloud_accounts)
        if sys.platform == 'darwin':
            file_menu.addSeparator()
            act(file_menu, 'Import from Apple Notes…', self._on_import_apple_notes)
        file_menu.addSeparator()
        act(file_menu, 'Quit', self.close, QKeySequence.StandardKey.Quit,
            role=QAction.MenuRole.QuitRole)

        edit_menu = mb.addMenu('&Edit')
        act(edit_menu, 'Find', self._focus_search, 'Ctrl+F')

        fmt_menu = mb.addMenu('F&ormat')
        act(fmt_menu, 'Bold', self._fmt_bold, 'Ctrl+B')
        act(fmt_menu, 'Italic', self._fmt_italic, 'Ctrl+I')
        act(fmt_menu, 'Underline', self._fmt_underline, 'Ctrl+U')
        fmt_menu.addSeparator()
        act(fmt_menu, 'Heading 1', self._fmt_h1, 'Ctrl+1')
        act(fmt_menu, 'Heading 2', self._fmt_h2, 'Ctrl+2')
        fmt_menu.addSeparator()
        act(fmt_menu, 'Text Colour…', self._fmt_color)

        # On macOS Qt relocates About / app-specific items into the
        # application menu; on Linux/Windows they stay under Help.
        help_menu = mb.addMenu('&Help')
        act(help_menu, 'About Nexon Notes', self._show_about,
            role=QAction.MenuRole.AboutRole)
        act(help_menu, 'Check for Updates…', lambda: self._check_for_updates(manual=True),
            role=QAction.MenuRole.ApplicationSpecificRole)

        if is_linux:
            # The in-window menu bar above otherwise sits there permanently,
            # unlike macOS's native top-of-screen bar. Auto-hide it and only
            # reveal it while the cursor hovers the top edge of the window,
            # so it behaves the same way visually as the macOS menu bar does.
            self._menu_bar = mb
            mb.setVisible(False)
            self._menu_reveal_timer = QTimer(self)
            self._menu_reveal_timer.setInterval(120)
            self._menu_reveal_timer.timeout.connect(self._update_menu_bar_visibility)
            self._menu_reveal_timer.start()

    def _update_menu_bar_visibility(self):
        mb = self._menu_bar
        if not self.isActiveWindow():
            mb.setVisible(False)
            return
        menu_open = any(a.menu() is not None and a.menu().isVisible() for a in mb.actions())
        if menu_open:
            mb.setVisible(True)
            return
        pos = self.mapFromGlobal(QCursor.pos())
        reveal_zone = mb.sizeHint().height() if mb.isVisible() else 6
        hovering = self.rect().contains(pos) and pos.y() <= reveal_zone
        if hovering != mb.isVisible():
            mb.setVisible(hovering)

    def _focus_search(self):
        self.search_entry.setFocus()
        self.search_entry.selectAll()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _mk_sidebar(self):
        sb = QWidget(); sb.setObjectName('sidebar')
        sb.setMinimumWidth(180); sb.setMaximumWidth(290)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Brand
        brand = QWidget()
        brand.setStyleSheet(f'background: {DARK_BG2};')
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(14, 14, 14, 12)
        bl.setSpacing(10)

        logo_lbl = QLabel()
        logo_pix = QPixmap(LOGO_PATH)
        if not logo_pix.isNull():
            logo_lbl.setPixmap(logo_pix.scaled(
                52, 52,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        logo_lbl.setFixedSize(52, 52)
        bl.addWidget(logo_lbl)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(0)
        name = QLabel('Nexon Notes')
        name.setObjectName('brand-name')
        name_col.addWidget(name)
        if APP_VERSION:
            version_lbl = QLabel(f'v{APP_VERSION}')
            version_lbl.setObjectName('brand-version')
            name_col.addWidget(version_lbl)
        bl.addLayout(name_col)
        bl.addStretch()
        lay.addWidget(brand)

        # Search
        self.search_entry = QLineEdit()
        self.search_entry.setObjectName('search-entry')
        self.search_entry.setPlaceholderText('🔍  Search notes…')
        self.search_entry.textChanged.connect(self._on_search)
        lay.addWidget(self.search_entry)

        # Section label + new-folder button
        sec_row = QWidget()
        sec_row.setStyleSheet('background: transparent;')
        sec_hl = QHBoxLayout(sec_row)
        sec_hl.setContentsMargins(0, 0, 8, 0)
        sec_hl.setSpacing(0)
        lbl = QLabel('FOLDERS')
        lbl.setObjectName('section-label')
        sec_hl.addWidget(lbl)
        sec_hl.addStretch()
        new_folder_btn = QPushButton('+')
        new_folder_btn.setToolTip('New Folder')
        new_folder_btn.setFixedSize(22, 22)
        new_folder_btn.setStyleSheet(f'''
            QPushButton {{
                background: transparent; border: 1px solid #5A4A4F;
                border-radius: 5px; color: #9A8A8F; font-size: 16px;
                font-weight: bold; padding-bottom: 2px;
            }}
            QPushButton:hover {{ background: #3D3438; color: white; border-color: #9A8A8F; }}
            QPushButton:pressed {{ background: #4A3C40; }}
        ''')
        new_folder_btn.clicked.connect(self._on_new_folder)
        sec_hl.addWidget(new_folder_btn)
        lay.addWidget(sec_row)

        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.setObjectName('folder-list')
        self.folder_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.folder_list.currentRowChanged.connect(self._on_folder_changed)
        self.folder_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list.customContextMenuRequested.connect(self._on_folder_context)
        lay.addWidget(self.folder_list, 1)  # stretch factor: eats extra space, not the footer below

        self.cloud_status_lbl = QLabel('')
        self.cloud_status_lbl.setObjectName('cloud-status-label')
        self.cloud_status_lbl.setWordWrap(True)
        lay.addWidget(self.cloud_status_lbl)

        cloud_accounts_btn = QPushButton('☁  Manage Cloud Accounts…')
        cloud_accounts_btn.setObjectName('cloud-accounts-btn')
        cloud_accounts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cloud_accounts_btn.clicked.connect(self._open_cloud_accounts)
        lay.addWidget(cloud_accounts_btn)

        return sb

    def _fill_sidebar(self):
        self._busy = True
        self.folder_list.clear()

        def add(key, icon, label, count):
            text = f'  {icon}  {label}' + (f'   {count}' if count else '')
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.folder_list.addItem(item)

        add('all', '📋', 'All Notes', self.db.all_count())
        for f in self.db.folders():
            add(f['name'], '📁', f['name'], f['count'])

        # Restore selection
        for i in range(self.folder_list.count()):
            if self.folder_list.item(i).data(Qt.ItemDataRole.UserRole) == self.current_folder:
                self.folder_list.setCurrentRow(i)
                break
        else:
            self.folder_list.setCurrentRow(0)

        self._busy = False

    # ── Notes panel ───────────────────────────────────────────────────────────
    def _mk_notes_panel(self):
        pn = QWidget(); pn.setObjectName('notes-panel')
        pn.setMinimumWidth(240); pn.setMaximumWidth(380)
        lay = QVBoxLayout(pn)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QWidget()
        hdr.setStyleSheet(f'background: {LIST_BG}; border-bottom: 1px solid #DCDCDC;')
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(10, 6, 10, 6)
        hl.setSpacing(8)

        self.panel_title = QLabel('All Notes')
        self.panel_title.setObjectName('panel-title')
        hl.addWidget(self.panel_title)
        hl.addStretch()
        lay.addWidget(hdr)

        btn = QPushButton('＋  New Note')
        btn.setObjectName('new-note-btn')
        btn.setFixedHeight(40)
        btn.setToolTip('New Note  Ctrl+N')
        btn.clicked.connect(self._on_new_note)
        lay.addWidget(btn)

        self.notes_list = QListWidget()
        self.notes_list.setObjectName('notes-list')
        self.notes_list.setSpacing(0)
        self.notes_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.notes_list.currentItemChanged.connect(self._on_note_selected)
        self.notes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.notes_list.customContextMenuRequested.connect(self._on_note_context)
        lay.addWidget(self.notes_list)
        return pn

    def _fill_notes(self, folder=None):
        self._busy = True
        folder = folder if folder is not None else self.current_folder
        self.notes_list.clear()

        notes = self.db.get_notes(folder)
        if not notes:
            ph = QListWidgetItem('No notes yet.\nClick + to create one.')
            ph.setFlags(Qt.ItemFlag.NoItemFlags)
            ph.setForeground(QColor('#AAAAAA'))
            ph.setSizeHint(QSize(0, 120))
            self.notes_list.addItem(ph)
        else:
            for note in notes:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, note['id'])
                item.setSizeHint(QSize(0, 72))
                self.notes_list.addItem(item)
                w = NoteRow(note)
                self.notes_list.setItemWidget(item, w)
                if note['id'] == self.current_note_id:
                    self.notes_list.setCurrentItem(item)
                    w.set_selected(True)

        self._busy = False

    # ── Editor ────────────────────────────────────────────────────────────────
    def _mk_editor(self):
        pn = QWidget(); pn.setObjectName('editor-panel')
        lay = QVBoxLayout(pn)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Toolbar
        tb = QWidget(); tb.setObjectName('editor-toolbar'); tb.setFixedHeight(38)
        tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(8, 4, 8, 4)
        tbl.setSpacing(2)

        btn_style = f'''
            QPushButton {{
                background: transparent; border: 1px solid transparent;
                border-radius: 5px; color: #444; font-size: 12px; font-weight: bold;
                max-height: 26px; min-height: 26px; min-width: 28px; padding: 1px 6px;
            }}
            QPushButton:hover {{ background: #F0F0F0; border-color: #DCDCDC; color: #111; }}
            QPushButton:checked {{ background: {ORANGE}; border-color: #C7420F; color: white; }}
        '''

        def tbtn(label, tip, slot, checkable=False):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFixedHeight(26)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            return b

        def vsep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setStyleSheet('color: #E0E0E0;')
            s.setFixedWidth(1)
            return s

        self.btn_bold   = tbtn('B',  'Bold  Ctrl+B',      self._fmt_bold,      True)
        self.btn_italic = tbtn('I',  'Italic  Ctrl+I',    self._fmt_italic,    True)
        self.btn_under  = tbtn('U',  'Underline  Ctrl+U', self._fmt_underline, True)
        tbl.addWidget(self.btn_bold)
        tbl.addWidget(self.btn_italic)
        tbl.addWidget(self.btn_under)
        tbl.addWidget(vsep())
        tbl.addWidget(tbtn('H1', 'Heading 1', self._fmt_h1))
        tbl.addWidget(tbtn('H2', 'Heading 2', self._fmt_h2))
        tbl.addWidget(vsep())

        # Font size spinner
        size_lbl = QLabel('Size:')
        size_lbl.setStyleSheet('color: #666; font-size: 11px; padding: 0 2px 0 4px;')
        tbl.addWidget(size_lbl)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 96)
        self.size_spin.setValue(14)
        self.size_spin.setSuffix(' pt')
        self.size_spin.setFixedHeight(24)
        self.size_spin.setFixedWidth(62)
        self.size_spin.setStyleSheet('''
            QSpinBox {
                border: 1px solid #DCDCDC; border-radius: 4px;
                font-size: 11px; padding: 1px 4px;
                background: white; color: #222;
            }
            QSpinBox:focus { border-color: #AAAAAA; }
        ''')
        self.size_spin.valueChanged.connect(self._on_size_changed)
        tbl.addWidget(self.size_spin)
        tbl.addWidget(vsep())

        # Text colour button (palette icon)
        self._text_color = QColor('#1A1A1A')
        self.btn_color = QPushButton('🎨')
        self.btn_color.setToolTip('Text colour')
        self.btn_color.setFixedSize(32, 26)
        self.btn_color.clicked.connect(self._fmt_color)
        self.btn_color.setStyleSheet('''
            QPushButton {
                background: transparent; border: 1px solid transparent;
                border-radius: 5px; font-size: 15px;
                min-width: 32px; max-width: 32px;
                min-height: 26px; max-height: 26px;
            }
            QPushButton:hover { background: #F0F0F0; border-color: #DCDCDC; }
            QPushButton:pressed { background: #E0E0E0; }
        ''')
        tbl.addWidget(self.btn_color)

        tbl.addStretch()
        self.folder_info_lbl = QLabel('')
        self.folder_info_lbl.setObjectName('folder-info-label')
        tbl.addWidget(self.folder_info_lbl)

        lay.addWidget(tb)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color: #E8E8E8;')
        lay.addWidget(sep)

        # Stack: placeholder / editor
        self.editor_stack = QStackedWidget()
        lay.addWidget(self.editor_stack)

        ph = QWidget(); ph.setStyleSheet(f'background: {EDITOR_BG};')
        phl = QVBoxLayout(ph)
        phl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for text, obj_name in [('📝', 'ph-icon'),
                                ('Select or create a note', 'ph-title'),
                                ('Saved to  ~/Notes/', 'ph-sub')]:
            lbl = QLabel(text)
            lbl.setObjectName(obj_name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            phl.addWidget(lbl)
        self.editor_stack.addWidget(ph)

        self.editor = PaperEditor()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_toolbar)
        self.editor_stack.addWidget(self.editor)

        self.editor_stack.setCurrentIndex(0)
        return pn

    # ── Editor open/close ─────────────────────────────────────────────────────
    def _open_editor(self, nid):
        note = self.db.get_note(nid)
        if not note:
            return
        self._busy = True
        self.editor.setPlainText(note['content'] or '')
        self._style_title()
        self.folder_info_lbl.setText(f"in {note['folder']}")
        self.editor_stack.setCurrentIndex(1)
        self._busy = False
        self.editor.setFocus()
        c = self.editor.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(c)

    def _close_editor(self):
        self._busy = True
        self.editor.setPlainText('')
        self.folder_info_lbl.setText('')
        self.editor_stack.setCurrentIndex(0)
        self._busy = False

    def _style_title(self):
        doc = self.editor.document()
        cur = QTextCursor(doc)
        cur.movePosition(QTextCursor.MoveOperation.Start)
        cur.movePosition(QTextCursor.MoveOperation.EndOfLine,
                         QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        f = QFont(); f.setPointSize(20); f.setBold(True)
        fmt.setFont(f)
        fmt.setForeground(QColor('#111111'))
        cur.mergeCharFormat(fmt)

    # ── Save ──────────────────────────────────────────────────────────────────
    def _on_text_changed(self):
        if not self._busy:
            self._save_timer.start(700)

    def _do_save(self):
        if not self.current_note_id:
            return
        self.db.save_note(self.current_note_id, self.editor.toPlainText())
        self._fill_notes()
        self._fill_sidebar()
        # Don't restart if already pending — otherwise continuous typing would
        # keep pushing this back forever and notes.db would never sync.
        if not self._cloud_debounce_timer.isActive():
            self._cloud_debounce_timer.start(10000)

    def _flush(self):
        self._save_timer.stop()
        self._do_save()

    # ── Cloud backup ──────────────────────────────────────────────────────────
    def _open_cloud_accounts(self):
        dlg = CloudAccountsDialog(self, cloud_sync=self.cloud, on_change=self._trigger_cloud_sync)
        dlg.exec()

    def _trigger_cloud_sync(self):
        self.cloud.sync_all_async(on_done=self._sync_signal.finished.emit)

    def _on_cloud_sync_done(self):
        if not self.cloud.status:
            self.cloud_status_lbl.setText('')
            return
        parts = []
        for label, info in sorted(self.cloud.status.items()):
            mark = '✓' if info['ok'] else '✕'
            parts.append(f"☁ {label} {mark} {info['when']}")
        self.cloud_status_lbl.setText('\n'.join(parts))

    # ── Apple Notes import ───────────────────────────────────────────────────
    def _on_import_apple_notes(self):
        box = QMessageBox(self)
        box.setWindowTitle('Import from Apple Notes')
        box.setText(
            'Copy notes from the Notes app into Nexon Notes, matched into '
            'folders of the same name (new folders are created as needed).\n\n'
            'Merge only adds notes you don\'t already have (matched by exact '
            'folder + content) — safe to run again after adding new notes in '
            'the Notes app.\n\n'
            'Wipe & Re-import removes every note a previous Apple Notes '
            'import created, then imports fresh. Notes you typed by hand in '
            'Nexon Notes are never touched by either option.\n\n'
            'macOS may ask you to authorize Nexon Notes to control Notes — '
            'this can take a little while for a large note library.'
        )
        merge_btn = box.addButton('Merge', QMessageBox.ButtonRole.AcceptRole)
        wipe_btn = box.addButton('Wipe && Re-import', QMessageBox.ButtonRole.DestructiveRole)
        box.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is merge_btn:
            mode = 'merge'
        elif clicked is wipe_btn:
            reply = QMessageBox.question(
                self, 'Wipe & Re-import',
                'This removes every note previously imported from Apple '
                'Notes and re-imports from scratch. Continue?',
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            mode = 'wipe'
        else:
            return

        self._import_progress = QMessageBox(self)
        self._import_progress.setWindowTitle('Import from Apple Notes')
        self._import_progress.setText('Importing notes…')
        self._import_progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        self._import_progress.setWindowModality(Qt.WindowModality.NonModal)
        self._import_progress.show()

        def worker():
            # Broad except is deliberate: this runs unsupervised on a
            # background thread, and _apply_apple_notes_import does real DB
            # writes — any exception here (a stray character in note
            # content, a locked DB, etc.) must still reach the GUI thread so
            # the progress dialog closes, instead of leaving it stuck
            # forever with no way for the user to tell what happened.
            try:
                notes = fetch_notes()
                count, skipped = self._apply_apple_notes_import(notes, mode)
                error = ''
            except Exception as e:
                count, skipped = 0, 0
                error = str(e) if isinstance(e, AppleNotesImportError) else \
                    f'Import failed: {e}'
            self._import_signal.done.emit(count, skipped, error)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_apple_notes_import(self, notes, mode):
        if mode == 'wipe':
            self.db.delete_apple_imported_notes()
            self.db.prune_empty_folders()

        existing_folders = {f['name'] for f in self.db.folders()}
        existing_pairs = self.db.imported_folder_content_pairs() if mode == 'merge' else set()
        count = 0
        skipped = 0
        for note in notes:
            folder = safe_folder_name(note['folder'])
            if folder not in existing_folders:
                self.db.new_folder(folder)
                existing_folders.add(folder)
            if mode == 'merge' and (folder, note['content']) in existing_pairs:
                skipped += 1
                continue
            # One bad note (encoding oddity, embedded control character from
            # a rich-content note, etc.) shouldn't abort an otherwise-good
            # import of a thousand-plus notes.
            try:
                self.db.import_apple_note(folder, note['content'])
                count += 1
            except Exception:
                continue
        return count, skipped

    def _on_apple_notes_import_done(self, count, skipped, error):
        self._import_progress.close()
        if error:
            QMessageBox.warning(self, 'Import from Apple Notes', error)
            return
        self._fill_sidebar()
        self._fill_notes(self.current_folder)
        msg = f'Imported {count} notes.'
        if skipped:
            msg += f' ({skipped} already up to date.)'
        QMessageBox.information(self, 'Import from Apple Notes', msg)

    # ── App updates ───────────────────────────────────────────────────────────
    def _check_for_updates(self, manual=False):
        if manual:
            # Triggered from the menu: report every outcome, not just updates.
            check_for_update_async(
                APP_VERSION,
                on_available=self._update_signal.available.emit,
                on_up_to_date=self._update_signal.up_to_date.emit,
                on_error=self._update_signal.failed.emit,
            )
        else:
            check_for_update_async(APP_VERSION, on_available=self._update_signal.available.emit)

    def _on_update_up_to_date(self):
        QMessageBox.information(
            self, 'Check for Updates',
            f'You are up to date.\nNexon Notes v{APP_VERSION} is the latest version.',
        )

    def _on_update_check_failed(self):
        QMessageBox.warning(
            self, 'Check for Updates',
            'Could not check for updates.\n'
            'Check your internet connection and try again.',
        )

    def _show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle('About Nexon Notes')
        logo_pix = QPixmap(LOGO_PATH)
        if not logo_pix.isNull():
            box.setIconPixmap(logo_pix.scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        box.setText(f'<b>Nexon Notes</b><br>Version {APP_VERSION or "unknown"}')
        box.setInformativeText(
            'A simple, native-feeling notes app.<br>'
            'Notes are stored locally in SQLite with optional cloud backup '
            'via rclone.<br><br>'
            '<a href="https://github.com/Aad6552/Nexon-Notes">'
            'github.com/Aad6552/Nexon-Notes</a>'
        )
        box.exec()

    def _on_update_available(self, latest_version):
        box = QMessageBox(self)
        box.setWindowTitle('Update Available')
        box.setText(
            f'A new version of Nexon Notes is available: v{latest_version}\n'
            f'(you have v{APP_VERSION}).'
        )
        update_btn = box.addButton('Update', QMessageBox.ButtonRole.AcceptRole)
        box.addButton('Not Now', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is update_btn:
            self._run_update()

    def _run_update(self):
        subprocess.Popen(['bash', GET_LATEST_RELEASE_SCRIPT])
        QMessageBox.information(
            self, 'Updating',
            'Nexon Notes is downloading the update and will now close.\n'
            'It will reopen automatically once the update finishes.',
        )
        QApplication.quit()

    # ── Toolbar state ─────────────────────────────────────────────────────────
    def _update_toolbar(self):
        fmt = self.editor.currentCharFormat()
        self.btn_bold.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
        self.btn_italic.setChecked(fmt.fontItalic())
        self.btn_under.setChecked(fmt.fontUnderline())
        # Sync size spinner (block signal to avoid loop)
        ps = fmt.font().pointSize()
        if ps > 0:
            self.size_spin.blockSignals(True)
            self.size_spin.setValue(ps)
            self.size_spin.blockSignals(False)
        # Track current colour for next picker open
        fg = fmt.foreground().color()
        if fg.isValid() and fg != QColor(0, 0, 0, 0):
            self._text_color = fg

    def _refresh_color_btn(self):
        pass  # icon is static emoji; no swatch update needed

    # ── Formatting ────────────────────────────────────────────────────────────
    def _apply_fmt(self, fmt):
        cur = self.editor.textCursor()
        if cur.hasSelection():
            cur.mergeCharFormat(fmt)
        else:
            self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _fmt_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Normal
            if self.editor.currentCharFormat().fontWeight() == QFont.Weight.Bold
            else QFont.Weight.Bold
        )
        self._apply_fmt(fmt)

    def _fmt_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.editor.currentCharFormat().fontItalic())
        self._apply_fmt(fmt)

    def _fmt_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.editor.currentCharFormat().fontUnderline())
        self._apply_fmt(fmt)

    def _fmt_h1(self):
        fmt = QTextCharFormat()
        f = QFont(); f.setPointSize(20); f.setBold(True); fmt.setFont(f)
        self._apply_fmt(fmt)

    def _fmt_h2(self):
        fmt = QTextCharFormat()
        f = QFont(); f.setPointSize(16); f.setBold(True); fmt.setFont(f)
        self._apply_fmt(fmt)

    def _on_size_changed(self, pts):
        fmt = QTextCharFormat()
        f = QFont(); f.setPointSize(pts); fmt.setFont(f)
        self._apply_fmt(fmt)

    def _fmt_color(self):
        chosen = QColorDialog.getColor(self._text_color, self, 'Text Colour')
        if not chosen.isValid():
            return
        self._text_color = chosen
        self._refresh_color_btn()
        fmt = QTextCharFormat()
        fmt.setForeground(chosen)
        self._apply_fmt(fmt)

    # ── Folder events ─────────────────────────────────────────────────────────
    def _on_folder_changed(self, row):
        if self._busy or row < 0:
            return
        item = self.folder_list.item(row)
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        self._flush()
        self.current_folder = key
        self.panel_title.setText('All Notes' if key == 'all' else key)

        if self.current_note_id:
            note = self.db.get_note(self.current_note_id)
            if note:
                stays = key == 'all' or note['folder'] == key
                if not stays:
                    self.current_note_id = None
                    self._close_editor()

        self._fill_notes(key)

    def _on_new_folder(self):
        name, ok = QInputDialog.getText(self, 'New Folder', 'Folder name:')
        name = name.strip()
        if not ok or not name:
            return
        if not self.db.new_folder(name):
            QMessageBox.warning(self, 'New Folder', f'A folder named "{name}" already exists.')
            return
        self.current_folder = name
        self._fill_sidebar()
        self._fill_notes(name)

    def _on_folder_context(self, pos):
        item = self.folder_list.itemAt(pos)
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key or key == 'all':
            return  # can't delete the virtual "All Notes" row

        menu = QMenu(self)
        act = menu.addAction(f'🗑  Delete Folder "{key}"')
        if menu.exec(self.folder_list.mapToGlobal(pos)) == act:
            reply = QMessageBox.question(
                self, 'Delete Folder',
                f'Delete folder "{key}" and all its notes?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.current_note_id:
                    note = self.db.get_note(self.current_note_id)
                    if note and note['folder'] == key:
                        self.current_note_id = None
                        self._close_editor()
                self.db.del_folder(key)
                if self.current_folder == key:
                    self.current_folder = 'all'
                self._fill_sidebar()
                self._fill_notes(self.current_folder)

    # ── Note events ───────────────────────────────────────────────────────────
    def _on_note_selected(self, current, previous):
        if self._busy or not current:
            return
        nid = current.data(Qt.ItemDataRole.UserRole)
        if not nid or nid == self.current_note_id:
            return
        if previous:
            w = self.notes_list.itemWidget(previous)
            if isinstance(w, NoteRow):
                w.set_selected(False)
        w = self.notes_list.itemWidget(current)
        if isinstance(w, NoteRow):
            w.set_selected(True)
        self._flush()
        self.current_note_id = nid
        self._open_editor(nid)

    def _on_new_note(self):
        self._flush()
        # Always create in the selected folder (or Notes if 'all')
        folder = 'Notes' if self.current_folder == 'all' else self.current_folder
        note = self.db.new_note(folder)
        self.current_note_id = note['id']

        # Switch to that folder so the new note is visible in the list
        self.current_folder = folder
        self.panel_title.setText(folder)
        self._fill_sidebar()      # updates selection in sidebar
        self._fill_notes(folder)  # rebuilds list; selects current_note_id
        self._open_editor(note['id'])

        # Ensure item is visually selected
        for i in range(self.notes_list.count()):
            item = self.notes_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == note['id']:
                self.notes_list.setCurrentItem(item)
                w = self.notes_list.itemWidget(item)
                if isinstance(w, NoteRow):
                    w.set_selected(True)
                break

    def _on_note_context(self, pos):
        item = self.notes_list.itemAt(pos)
        if not item:
            return
        nid = item.data(Qt.ItemDataRole.UserRole)
        if not nid:
            return
        menu = QMenu(self)
        move = menu.addMenu('📁  Move to Folder')
        for f in self.db.folders():
            move.addAction(f['name']).setData(('move', nid, f['name']))
        menu.addSeparator()
        del_act = menu.addAction('🗑  Delete Note')
        action = menu.exec(self.notes_list.mapToGlobal(pos))
        if not action:
            return
        if action == del_act:
            reply = QMessageBox.question(
                self, 'Delete Note', 'Permanently delete this note?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.current_note_id == nid:
                    self.current_note_id = None
                    self._close_editor()
                self.db.del_note(nid)
                self._fill_notes()
                self._fill_sidebar()
            return
        data = action.data()
        if isinstance(data, tuple) and data[0] == 'move':
            _, mid, folder = data
            self.db.move_note(mid, folder)
            self._fill_notes()
            self._fill_sidebar()

    # ── Search ────────────────────────────────────────────────────────────────
    def _on_search(self, text):
        q = text.strip()
        if not q:
            self.panel_title.setText('All Notes' if self.current_folder == 'all'
                                     else self.current_folder)
            self._fill_notes()
            return
        self._busy = True
        self.notes_list.clear()
        results = self.db.search(q)
        self.panel_title.setText(f'"{q}"  —  {len(results)} result{"s" if len(results)!=1 else ""}')
        if results:
            for note in results:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, note['id'])
                item.setSizeHint(QSize(0, 72))
                self.notes_list.addItem(item)
                self.notes_list.setItemWidget(item, NoteRow(note))
        else:
            ph = QListWidgetItem('No results found.')
            ph.setFlags(Qt.ItemFlag.NoItemFlags)
            ph.setForeground(QColor('#AAAAAA'))
            ph.setSizeHint(QSize(0, 100))
            self.notes_list.addItem(ph)
        self._busy = False

    # ── Init reload ───────────────────────────────────────────────────────────
    def _reload_all(self):
        self._fill_sidebar()
        self._fill_notes('all')

    def closeEvent(self, ev):
        self._flush()
        # Best-effort: fire off a last sync attempt but don't make the user
        # wait for it. Cloud backup already happens continuously while the
        # app is open (every 5s, plus ~10s after you stop typing),
        # so the only risk here is losing the last few seconds of edits.
        # Waiting on it here — even off the GUI thread with a bounded
        # failsafe — still kept the process alive for that whole bound with
        # no window to show for it, which is exactly what the desktop
        # treats as an unresponsive app ("Force Quit?") even though nothing
        # was actually frozen.
        self.cloud.sync_all_async()
        ev.accept()


# ── Entry point ───────────────────────────────────────────────────────────────
_lock_file = None  # kept open for the process lifetime — closing it releases the lock


def _fix_macos_app_name():
    """macOS takes the menu-bar app name from the running process's bundle,
    which is "Python" when launched from a plain interpreter — no Qt API
    changes it. Rewrite the bundle's name in-place before the app starts.
    Needs pyobjc-framework-Cocoa (run.sh installs it on macOS); harmless
    no-op everywhere else."""
    if sys.platform != 'darwin':
        return
    try:
        from Foundation import NSBundle
    except ImportError:
        return
    bundle = NSBundle.mainBundle()
    if bundle is None:
        return
    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
    if info is not None:
        info['CFBundleName'] = 'Nexon Notes'
        info['CFBundleDisplayName'] = 'Nexon Notes'


def _acquire_single_instance_lock():
    """Refuse to start a second copy: two instances writing notes.db at once
    risks corruption, and a second "Connect" while one is mid sign-in fails
    with a confusing port-already-in-use error instead of a clear message."""
    global _lock_file
    os.makedirs(NOTES_DIR, exist_ok=True)
    _lock_file = open(os.path.join(NOTES_DIR, '.nexon-notes.lock'), 'w')
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def main():
    _fix_macos_app_name()
    app = QApplication(sys.argv)
    app.setApplicationName('Nexon Notes')
    app.setApplicationDisplayName('Nexon Notes')
    app.setApplicationVersion(APP_VERSION)
    # Since we run as "python3 nexon_notes.py" rather than a native binary, the
    # window's WM_CLASS is "python3" by default, so Linux desktop shells can't
    # match the running window to nexon-notes.desktop and fall back to a
    # generic icon/name in the taskbar. This tells them which entry to use.
    app.setDesktopFileName('nexon-notes')
    app.setStyleSheet(STYLE)

    logo_pix = QPixmap(LOGO_PATH)
    if not logo_pix.isNull():
        app.setWindowIcon(QIcon(logo_pix))

    if not _acquire_single_instance_lock():
        QMessageBox.warning(
            None, 'Nexon Notes',
            'Nexon Notes is already running.\n\n'
            'Check your other windows/Activities — a second copy '
            "can't safely share the same notes.",
        )
        sys.exit(1)

    db  = DB()
    win = MainWindow(db)
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
