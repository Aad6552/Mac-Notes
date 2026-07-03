"""Sign-in dialog for Proton Drive / Google Drive / Microsoft OneDrive."""

import threading

from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QWidget,
    QLabel, QPushButton, QLineEdit, QMessageBox,
)

import cloud_login as cl


class _LoginSignal(QObject):
    status = pyqtSignal(str, str)       # rtype, message
    url = pyqtSignal(str, str)          # rtype, login url
    done = pyqtSignal(str, bool, str)   # rtype, ok, message


class CloudAccountsDialog(QDialog):
    def __init__(self, parent=None, on_change=None):
        super().__init__(parent)
        self.setWindowTitle('Cloud Accounts')
        self.setMinimumWidth(440)
        self._on_change = on_change
        self._signal = _LoginSignal()
        self._signal.status.connect(self._on_status)
        self._signal.url.connect(self._on_url)
        self._signal.done.connect(self._on_done)
        self._pending_urls = {}  # rtype -> url, for the "Copy Link" fallback

        self._remotes = cl.list_remotes()
        self._rows = {}

        lay = QVBoxLayout(self)
        title = QLabel(
            'Sign in and Ubuntu Notes backs up automatically to a '
            '"notes" folder on each drive.'
        )
        title.setWordWrap(True)
        lay.addWidget(title)

        for rtype, label in cl.PROVIDER_TYPES:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 8, 0, 8)
            name_lbl = QLabel(label)
            name_lbl.setMinimumWidth(150)
            status_lbl = QLabel()
            status_lbl.setWordWrap(True)
            copy_btn = QPushButton('Copy Link')
            copy_btn.setVisible(False)
            copy_btn.clicked.connect(lambda _checked, t=rtype: self._copy_url(t))
            btn = QPushButton()
            btn.clicked.connect(lambda _checked, t=rtype: self._on_click(t))
            hl.addWidget(name_lbl)
            hl.addWidget(status_lbl, 1)
            hl.addWidget(copy_btn)
            hl.addWidget(btn)
            lay.addWidget(row)
            self._rows[rtype] = {'status': status_lbl, 'btn': btn, 'copy_btn': copy_btn}
            self._refresh_row(rtype)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

    # ── Row state ─────────────────────────────────────────────────────────────
    def _refresh_row(self, rtype):
        widgets = self._rows[rtype]
        name = self._remotes.get(rtype)
        widgets['copy_btn'].setVisible(False)
        self._pending_urls.pop(rtype, None)
        if name:
            widgets['status'].setText(f'Connected  ({name})')
            widgets['btn'].setText('Disconnect')
        else:
            widgets['status'].setText('Not connected')
            widgets['btn'].setText('Connect')
        widgets['btn'].setEnabled(True)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _on_click(self, rtype):
        name = self._remotes.get(rtype)
        if name:
            label = dict(cl.PROVIDER_TYPES)[rtype]
            reply = QMessageBox.question(
                self, 'Disconnect', f'Stop backing up notes to {label}?'
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            cl.disconnect(name)
            del self._remotes[rtype]
            self._refresh_row(rtype)
            if self._on_change:
                self._on_change()
            return

        if rtype == 'protondrive':
            self._proton_login_flow(rtype)
        else:
            self._oauth_login_flow(rtype)

    def _oauth_login_flow(self, rtype):
        # Google/OneDrive both use the same local OAuth callback port, so
        # only one browser sign-in can be in flight at a time — block the
        # other Connect buttons rather than let them collide on it.
        for other_rtype in ('drive', 'onedrive'):
            self._rows[other_rtype]['btn'].setEnabled(False)
        widgets = self._rows[rtype]
        widgets['status'].setText('Opening your browser to sign in…')
        remote_name = cl.DEFAULT_REMOTE_NAMES[rtype]

        def worker():
            cl.login_oauth(
                rtype, remote_name,
                on_status=lambda msg: self._signal.status.emit(rtype, msg),
                on_url=lambda url: self._signal.url.emit(rtype, url),
                on_done=lambda ok, msg: self._signal.done.emit(rtype, ok, msg),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _proton_login_flow(self, rtype):
        dlg = QDialog(self)
        dlg.setWindowTitle('Sign in to Proton Drive')
        form = QFormLayout(dlg)
        email = QLineEdit()
        pw = QLineEdit()
        pw.setEchoMode(QLineEdit.EchoMode.Password)
        twofa = QLineEdit()
        twofa.setPlaceholderText('leave blank if not enabled')
        form.addRow('Email', email)
        form.addRow('Password', pw)
        form.addRow('2FA code', twofa)
        btn = QPushButton('Sign in')
        form.addRow(btn)

        def submit():
            if not email.text().strip() or not pw.text():
                return
            e, p, code = email.text().strip(), pw.text(), twofa.text().strip()
            dlg.accept()
            widgets = self._rows[rtype]
            widgets['btn'].setEnabled(False)
            widgets['status'].setText('Signing in…')
            remote_name = cl.DEFAULT_REMOTE_NAMES[rtype]

            def worker():
                cl.login_proton(
                    e, p, code, remote_name,
                    on_done=lambda ok, msg: self._signal.done.emit(rtype, ok, msg),
                )

            threading.Thread(target=worker, daemon=True).start()

        btn.clicked.connect(submit)
        dlg.exec()

    # ── Async callbacks (marshalled to the GUI thread via signals) ─────────────
    def _on_status(self, rtype, msg):
        self._rows[rtype]['status'].setText(msg)

    def _on_url(self, rtype, url):
        self._pending_urls[rtype] = url
        self._rows[rtype]['copy_btn'].setVisible(True)
        # Try opening it ourselves — more reliable from inside a GUI app
        # than the xdg-open rclone's own subprocess attempts.
        QDesktopServices.openUrl(QUrl(url))

    def _copy_url(self, rtype):
        url = self._pending_urls.get(rtype)
        if url:
            QApplication.clipboard().setText(url)
            self._rows[rtype]['status'].setText('Link copied — paste it into your browser')

    def _on_done(self, rtype, ok, msg):
        if ok:
            self._remotes = cl.list_remotes()
        else:
            QMessageBox.warning(self, 'Sign-in failed', msg)
        self._refresh_row(rtype)
        if rtype in ('drive', 'onedrive'):
            # Both share the OAuth port and were blocked together — unblock
            # together too, regardless of which one just finished.
            for other_rtype in ('drive', 'onedrive'):
                if other_rtype != rtype:
                    self._rows[other_rtype]['btn'].setEnabled(True)
        if self._on_change:
            self._on_change()
