from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QProgressBar, QPushButton, QVBoxLayout)

from ..db.migrations import connect
from ..db.repository import Repository
from ..importers import er1_import
from ..importers.vendor_import import parse_merge, run_import
from . import workers
from .i18n import tr


class _RunDialog(QDialog):
    done = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None
        self.worker = None
        self.result = None
        self.v = QVBoxLayout(self)
        self.status = QLabel("")
        self.bar = QProgressBar()
        self.run_btn = QPushButton(tr("run"))
        self.cancel_btn = QPushButton(tr("close"))
        self.cancel_btn.clicked.connect(self._cancel)

    def _finish_layout(self):
        h = QHBoxLayout()
        h.addWidget(self.run_btn)
        h.addWidget(self.cancel_btn)
        self.v.addWidget(self.status)
        self.v.addWidget(self.bar)
        self.v.addLayout(h)

    def _start(self, fn):
        self.run_btn.setEnabled(False)
        self.cancel_btn.setText(tr("cancel"))
        self.worker = workers.Worker(fn)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(self._done)
        self.worker.failed.connect(lambda m: self._done(None, m))
        self.thread = workers.start(self.worker, self)

    def _progress(self, i, n, text):
        self.bar.setMaximum(max(n, 1))
        self.bar.setValue(i)
        self.status.setText(text)

    def _done(self, res, err=None):
        self.result = res
        self.run_btn.setEnabled(True)
        self.cancel_btn.setText(tr("close"))
        self.status.setText(f"{tr('error')}: {err}" if err else self.describe(res))
        self.done.emit(res)

    def describe(self, res):
        return str(res)

    def _cancel(self):
        if self.thread and self.thread.isRunning():
            self.worker.cancel()
        else:
            self.accept()

    def wait(self, ms=120000):
        if self.thread:
            self.thread.wait(ms)

    def closeEvent(self, e):
        if self.worker:
            self.worker.cancel()
        self.wait()
        super().closeEvent(e)


class ImportDialog(_RunDialog):
    """Import R files from a folder or a detected ER1 USB drive."""

    def __init__(self, db_file: Path, data_dir: Path, patient_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("import_ecg").rstrip("…"))
        self.db_file, self.data_dir, self.patient_id = Path(db_file), Path(data_dir), patient_id
        self.files: list[Path] = []
        h = QHBoxLayout()
        b_folder = QPushButton(tr("folder"))
        b_usb = QPushButton(tr("detect_usb"))
        h.addWidget(b_folder)
        h.addWidget(b_usb)
        self.v.addLayout(h)
        self.list = QListWidget()
        self.v.addWidget(self.list)
        self.run_btn.setText(tr("import"))
        self._finish_layout()
        b_folder.clicked.connect(self._pick)
        b_usb.clicked.connect(self.detect)
        self.run_btn.clicked.connect(self.start_import)
        self.run_btn.setEnabled(False)

    def set_folder(self, folder: Path):
        self.files = er1_import.find_r_files(folder)
        self.list.clear()
        self.list.addItems([f.name for f in self.files])
        self.status.setText(tr("files_found", len(self.files)))
        self.run_btn.setEnabled(bool(self.files))

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, tr("folder"))
        if d:
            self.set_folder(Path(d))

    def detect(self, roots=None):
        drives = er1_import.detect_er1_drives(roots if isinstance(roots, list) else None)
        if drives:
            self.set_folder(drives[0])
        else:
            self.status.setText(tr("no_drive"))

    def start_import(self):
        files, db_file, data_dir, pid = list(self.files), self.db_file, self.data_dir, self.patient_id

        def job(progress, cancelled):
            conn = connect(db_file)  # own connection per thread
            try:
                return er1_import.import_r_files(Repository(conn), data_dir, files, pid,
                                                 progress=progress, cancelled=cancelled)
            finally:
                conn.close()

        self._start(job)

    def describe(self, res):
        return tr("import_done", len(res.imported), len(res.skipped), len(res.errors))


class VendorMigrationDialog(_RunDialog):
    def __init__(self, data_dir: Path, default_vendor: Path | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("migrate_vendor").rstrip("…"))
        self.data_dir = Path(data_dir)
        self.v.addWidget(QLabel(tr("vendor_folder")))
        h = QHBoxLayout()
        self.folder = QLineEdit(str(default_vendor or ""))
        b = QPushButton("…")
        b.clicked.connect(self._pick)
        h.addWidget(self.folder, 1)
        h.addWidget(b)
        self.v.addLayout(h)
        self.v.addWidget(QLabel(tr("merge_subusers")))
        self.merge = QLineEdit("2=1")
        self.v.addWidget(self.merge)
        self.dry = QCheckBox(tr("dry_run"))
        self.v.addWidget(self.dry)
        self._finish_layout()
        self.run_btn.clicked.connect(self.start_migration)

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, tr("vendor_folder"))
        if d:
            self.folder.setText(d)

    def start_migration(self):
        try:
            merge = parse_merge([s for s in self.merge.text().replace(",", " ").split() if s])
        except ValueError as e:
            self.status.setText(f"{tr('error')}: {e}")
            return
        vendor, target, dry = Path(self.folder.text()), self.data_dir, self.dry.isChecked()
        self._start(lambda progress, cancelled: run_import(vendor, target, dry_run=dry, merge=merge))

    def describe(self, res):
        return res.summary() if res else ""
