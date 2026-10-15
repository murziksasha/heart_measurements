from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QAbstractTableModel, QModelIndex, Qt

from ..db.repository import Repository
from .i18n import tr


def fmt_duration(sec: float) -> str:
    s = int(round(sec))
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{s:02d}"


class PatientListModel(QAbstractListModel):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.items = []
        self.refresh()

    def refresh(self):
        self.beginResetModel()
        self.items = self.repo.patients.list(order="name COLLATE NOCASE")
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        p = self.items[index.row()]
        if role == Qt.DisplayRole:
            return p.name
        if role == Qt.UserRole:
            return p
        return None

    def row_of(self, patient_id):
        return next((i for i, p in enumerate(self.items) if p.id == patient_id), -1)


class RecordingTableModel(QAbstractTableModel):
    COLS = ("start_time", "duration", "device", "analysis")

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.rows = []
        self.patient_id = None

    def set_patient(self, patient_id):
        self.patient_id = patient_id
        self.refresh()

    def refresh(self):
        self.beginResetModel()
        self.rows = []
        if self.patient_id is not None:
            devs = {d.id: d.serial for d in self.repo.devices.list()}
            for r in self.repo.recordings.for_patient(self.patient_id):
                srcs = sorted({a.source for a in self.repo.analysis.for_recording(r.id)})
                status = ", ".join(tr(f"status_{s}") for s in srcs) or tr("status_none")
                self.rows.append((r, devs.get(r.device_id, ""), status))
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return tr(self.COLS[section])
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, dev, status = self.rows[index.row()]
        if role == Qt.UserRole:
            return r
        if role == Qt.DisplayRole:
            return (r.start_time, fmt_duration(r.duration_s), dev, status)[index.column()]
        return None
