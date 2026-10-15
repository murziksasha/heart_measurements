from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QListView, QMainWindow,
                               QMessageBox, QPushButton, QSplitter, QTableView, QTabWidget,
                               QVBoxLayout, QWidget)

from ..db.repository import Repository
from . import i18n
from .dialogs import DevicesDialog, PatientDialog
from .i18n import tr
from .import_dialog import ImportDialog, VendorMigrationDialog
from .models import PatientListModel, RecordingTableModel
from .viewer import EcgViewer


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository, data_dir: Path, db_file: Path, vendor_default: Path | None = None):
        super().__init__()
        self.repo, self.data_dir, self.db_file = repo, Path(data_dir), Path(db_file)
        self.vendor_default = vendor_default
        self.setWindowTitle(tr("app_title"))
        self.resize(1280, 800)

        # sidebar
        side = QWidget()
        sv = QVBoxLayout(side)
        sv.addWidget(QLabel(f"<b>{tr('patients')}</b>"))
        self.patients = PatientListModel(repo, self)
        self.patient_view = QListView()
        self.patient_view.setModel(self.patients)
        sv.addWidget(self.patient_view, 1)
        hb = QHBoxLayout()
        self.btn_add, self.btn_edit, self.btn_del = (QPushButton(tr(k)) for k in ("add", "edit", "delete"))
        for b in (self.btn_add, self.btn_edit, self.btn_del):
            hb.addWidget(b)
        sv.addLayout(hb)

        # recordings + viewer
        self.recordings = RecordingTableModel(repo, self)
        self.rec_view = QTableView()
        self.rec_view.setModel(self.recordings)
        self.rec_view.setSelectionBehavior(QTableView.SelectRows)
        self.rec_view.setSelectionMode(QTableView.SingleSelection)
        self.rec_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rec_view.verticalHeader().hide()
        self.viewer = EcgViewer(repo.settings.get("mv_height_scale", 1.0) or 1.0)
        self.report = QLabel(tr("report_placeholder"))
        self.report.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.report.setWordWrap(True)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.viewer, tr("viewer"))
        self.tabs.addTab(self.report, tr("report"))
        right = QSplitter(Qt.Vertical)
        rec_box = QWidget()
        rv = QVBoxLayout(rec_box)
        rv.addWidget(QLabel(f"<b>{tr('recordings')}</b>"))
        rv.addWidget(self.rec_view)
        right.addWidget(rec_box)
        right.addWidget(self.tabs)
        right.setSizes([250, 550])
        split = QSplitter()
        split.addWidget(side)
        split.addWidget(right)
        split.setSizes([260, 1020])
        self.setCentralWidget(split)

        self._menus()
        self.patient_view.selectionModel().currentChanged.connect(self._patient_changed)
        self.rec_view.selectionModel().currentRowChanged.connect(self._recording_changed)
        self.btn_add.clicked.connect(self.add_patient)
        self.btn_edit.clicked.connect(self.edit_patient)
        self.btn_del.clicked.connect(self.delete_patient)
        if self.patients.rowCount():
            self.select_patient_row(0)

    def _menus(self):
        m = self.menuBar().addMenu(tr("file"))
        self.act_import = QAction(tr("import_ecg"), self, triggered=self.open_import)
        self.act_migrate = QAction(tr("migrate_vendor"), self, triggered=self.open_migration)
        self.act_devices = QAction(tr("devices"), self, triggered=self.open_devices)
        for a in (self.act_import, self.act_migrate, self.act_devices):
            m.addAction(a)
        m.addSeparator()
        m.addAction(QAction(tr("quit"), self, triggered=self.close))
        lm = self.menuBar().addMenu(tr("language"))
        grp = QActionGroup(self)
        for code, label in i18n.LANGUAGES.items():
            a = QAction(label, self, checkable=True, checked=code == i18n.language())
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
            grp.addAction(a)
            lm.addAction(a)

    # selection ------------------------------------------------------------
    def current_patient(self):
        idx = self.patient_view.currentIndex()
        return self.patients.data(idx, Qt.UserRole) if idx.isValid() else None

    def select_patient_row(self, row):
        self.patient_view.setCurrentIndex(self.patients.index(row))

    def _patient_changed(self, *_):
        p = self.current_patient()
        self.recordings.set_patient(p.id if p else None)
        if self.recordings.rowCount():
            self.rec_view.selectRow(0)

    def _recording_changed(self, cur, _prev):
        if not cur.isValid():
            return
        r = self.recordings.data(self.recordings.index(cur.row(), 0), Qt.UserRole)
        self.open_recording(r)

    def open_recording(self, r):
        if r.pcm_path and (self.data_dir / r.pcm_path).exists():
            self.viewer.load_pcm(self.data_dir / r.pcm_path, r.start_time)
        res = self.repo.analysis.for_recording(r.id)
        files = [a.pdf_path for a in res if a.pdf_path]
        self.report.setText(tr("report_placeholder") + ("\n\n" + tr("report_files", ", ".join(files)) if files else ""))

    # patients -------------------------------------------------------------
    def _reload_patients(self, select_id=None):
        self.patients.refresh()
        row = self.patients.row_of(select_id) if select_id else 0
        if self.patients.rowCount():
            self.select_patient_row(max(row, 0))
        else:
            self.recordings.set_patient(None)

    def add_patient(self, dialog_factory=PatientDialog):
        d = dialog_factory(None, self)
        if d.exec():
            p = self.repo.patients.add(d.result_patient())
            self._reload_patients(p.id)

    def edit_patient(self, dialog_factory=PatientDialog):
        p = self.current_patient()
        if p is None:
            return
        d = dialog_factory(p, self)
        if d.exec():
            self.repo.patients.update(d.result_patient())
            self._reload_patients(p.id)

    def delete_patient(self, confirm=None):
        p = self.current_patient()
        if p is None:
            return
        ok = confirm(p) if confirm else QMessageBox.question(
            self, tr("delete"), tr("confirm_delete_patient", p.name)) == QMessageBox.Yes
        if ok:
            self.repo.patients.delete(p.id)  # recording files on disk are kept
            self._reload_patients()

    # dialogs --------------------------------------------------------------
    def open_import(self):
        p = self.current_patient()
        if p is None:
            QMessageBox.information(self, tr("import"), tr("select_patient_first"))
            return
        ImportDialog(self.db_file, self.data_dir, p.id, self).exec()
        self.recordings.refresh()

    def open_migration(self):
        VendorMigrationDialog(self.data_dir, self.vendor_default, self).exec()
        self._reload_patients()

    def open_devices(self):
        DevicesDialog(self.repo, self).exec()
        self.recordings.refresh()

    def set_language(self, code):
        self.repo.settings.set("ui_language", code)
        QMessageBox.information(self, tr("language"), tr("restart_hint"))
