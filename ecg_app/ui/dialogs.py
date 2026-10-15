from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QSpinBox, QVBoxLayout)

from ..core.models import Device, Patient
from ..db.repository import Repository
from .i18n import tr


class PatientDialog(QDialog):
    def __init__(self, patient: Patient | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("patient"))
        self.patient = patient or Patient(name="")
        f = QFormLayout(self)
        self.name = QLineEdit(self.patient.name)
        self.gender = QComboBox()
        for key in ("unknown", "male", "female"):
            self.gender.addItem(tr(key), None if key == "unknown" else key)
        self.gender.setCurrentIndex(max(0, self.gender.findData(self.patient.gender)))
        self.birthday = QDateEdit()
        self.birthday.setDisplayFormat("yyyy-MM-dd")
        self.birthday.setCalendarPopup(True)
        self.birthday.setSpecialValueText(" ")
        self.birthday.setMinimumDate(QDate(1900, 1, 1))
        d = QDate.fromString(self.patient.birthday or "", "yyyy-MM-dd")
        self.birthday.setDate(d if d.isValid() else self.birthday.minimumDate())
        self.height = QSpinBox(maximum=250)
        self.height.setValue(self.patient.height_cm or 0)
        self.weight = QSpinBox(maximum=400)
        self.weight.setValue(self.patient.weight_kg or 0)
        self.contact = QLineEdit(self.patient.contact or "")
        for k, w in (("name", self.name), ("gender", self.gender), ("birthday", self.birthday),
                     ("height", self.height), ("weight", self.weight), ("contact", self.contact)):
            f.addRow(tr(k), w)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        f.addRow(self.buttons)
        self.name.textChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.name.text().strip()))

    def result_patient(self) -> Patient:
        p = self.patient
        p.name = self.name.text().strip()
        p.gender = self.gender.currentData()
        b = self.birthday.date()
        p.birthday = None if b == self.birthday.minimumDate() else b.toString("yyyy-MM-dd")
        p.height_cm = self.height.value() or None
        p.weight_kg = self.weight.value() or None
        p.contact = self.contact.text().strip() or None
        return p


class DevicesDialog(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(tr("devices").rstrip("…"))
        v = QVBoxLayout(self)
        self.list = QListWidget()
        v.addWidget(self.list)
        h = QHBoxLayout()
        self.bind_btn = QPushButton(tr("bind"))
        self.unbind_btn = QPushButton(tr("unbind"))
        close = QPushButton(tr("close"))
        for b in (self.bind_btn, self.unbind_btn, close):
            h.addWidget(b)
        v.addLayout(h)
        self.bind_btn.clicked.connect(self._ask_bind)
        self.unbind_btn.clicked.connect(self.unbind_selected)
        close.clicked.connect(self.accept)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for d in self.repo.devices.list(order="serial"):
            it = QListWidgetItem(f"{d.model}  {d.serial}")
            it.setData(256, d.id)
            self.list.addItem(it)

    def bind(self, serial: str) -> bool:
        serial = serial.strip()
        if not serial.isdigit() or self.repo.devices.by("serial", serial):
            return False
        self.repo.devices.add(Device(serial=serial))
        self.refresh()
        return True

    def _ask_bind(self):
        s, ok = QInputDialog.getText(self, tr("bind"), tr("serial_prompt"))
        if ok:
            self.bind(s)

    def unbind_selected(self):
        it = self.list.currentItem()
        if it:
            self.repo.devices.delete(it.data(256))  # recordings keep data, device_id -> NULL
            self.refresh()
