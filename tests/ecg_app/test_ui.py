import shutil
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtCore import Qt  # noqa: E402

from ecg_app.core.models import Patient  # noqa: E402
from ecg_app.db.migrations import connect  # noqa: E402
from ecg_app.db.repository import Repository  # noqa: E402
from ecg_app.importers.vendor_import import run_import  # noqa: E402
from ecg_app.ui import i18n  # noqa: E402
from ecg_app.ui.dialogs import DevicesDialog, PatientDialog  # noqa: E402
from ecg_app.ui.import_dialog import ImportDialog, VendorMigrationDialog  # noqa: E402
from ecg_app.ui.main_window import MainWindow  # noqa: E402
from ecg_app.ui.viewer import EcgViewer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SUB1 = ROOT / "Data" / "DATA" / "userfiles" / "subusr" / "1"
STAMP = "20261004161900"


@pytest.fixture
def small_vendor(tmp_path):
    v = tmp_path / "vendor"
    d = v / "DATA" / "userfiles" / "subusr" / "1"
    d.mkdir(parents=True)
    shutil.copy2(ROOT / "Data" / "DATA" / "db_lepu_care_world.db", v / "DATA")
    shutil.copy2(ROOT / "Data" / "config.ini", v)
    for n in (f"2306490032R{STAMP}", f"2306490032{STAMP}", f"report_1_2306490032_{STAMP}.json",
              f"Record_1_2306490032_{STAMP}Report.pdf"):
        shutil.copy2(SUB1 / n, d)
    return v


@pytest.fixture
def app_data(tmp_path, small_vendor):
    data = tmp_path / "data"
    run_import(small_vendor, data, merge={2: 1})
    repo = Repository(connect(data / "ecg_app.db"))
    yield repo, data
    repo.conn.close()


@pytest.fixture
def window(qtbot, app_data):
    repo, data = app_data
    w = MainWindow(repo, data, data / "ecg_app.db")
    qtbot.addWidget(w)
    w.show()
    return w


def test_i18n():
    i18n.set_language(0)  # legacy vendor int -> default
    assert i18n.language() == "uk" and i18n.tr("patients") == "Пацієнти"
    i18n.set_language("en")
    assert i18n.tr("patients") == "Patients"
    i18n.set_language("uk")


def test_window_loads_real_data(window):
    assert window.patients.rowCount() == 1
    assert window.recordings.rowCount() == 1
    assert window.recordings.data(window.recordings.index(0, 1)) == "0:02:45"
    assert window.recordings.data(window.recordings.index(0, 3)) == "Хмара"
    assert window.viewer.duration_s() == pytest.approx(165)
    assert "cloud_report.pdf" in window.report.text()


class _FakeDialog:
    def __init__(self, patient):
        self.patient = patient

    def exec(self):
        return True

    def result_patient(self):
        return self.patient


def test_patient_crud_via_window(window):
    window.add_patient(lambda p, parent: _FakeDialog(Patient(name="Іван", gender="male")))
    assert [p.name for p in window.patients.items] == ["Grygoriev", "Іван"]
    assert window.current_patient().name == "Іван"
    assert window.recordings.rowCount() == 0

    def edit(p, parent):
        p.name = "Іван Петренко"
        return _FakeDialog(p)
    window.edit_patient(edit)
    assert window.current_patient().name == "Іван Петренко"
    window.delete_patient(confirm=lambda p: True)
    assert [p.name for p in window.patients.items] == ["Grygoriev"]


def test_patient_dialog(qtbot):
    d = PatientDialog(Patient(name="A", gender="female", birthday="1985-02-20", height_cm=170))
    qtbot.addWidget(d)
    d.name.setText("  ")
    assert not d.buttons.button(d.buttons.StandardButton.Ok).isEnabled()
    d.name.setText("Олена")
    p = d.result_patient()
    assert (p.name, p.gender, p.birthday, p.height_cm, p.weight_kg) == ("Олена", "female", "1985-02-20", 170, None)


def test_devices_dialog(qtbot, app_data):
    repo, _ = app_data
    d = DevicesDialog(repo)
    qtbot.addWidget(d)
    assert d.list.count() == 1
    assert d.bind("1234567890") and not d.bind("1234567890") and not d.bind("abc")
    assert d.list.count() == 2
    d.list.setCurrentRow(0)
    d.unbind_selected()
    assert d.list.count() == 1


def test_viewer_real_pcm(qtbot):
    v = EcgViewer(mv_height_scale=2.0)
    qtbot.addWidget(v)
    v.load_pcm(SUB1 / f"2306490032{STAMP}")
    assert v.samples.dtype == np.int16 and len(v.samples) == 41250
    assert v.mv[100] == pytest.approx(v.samples[100] * 0.002467 * 2.0)
    lo, hi = v.plot.getViewBox().viewRange()[0]
    assert hi - lo == pytest.approx(10, abs=0.5)
    v.scroll.setValue(500)
    assert v.plot.getViewBox().viewRange()[0][0] == pytest.approx(50, abs=0.5)
    v.paper.setChecked(False)
    v.paper.setChecked(True)


def test_import_worker(qtbot, app_data, tmp_path):
    repo, data = app_data
    src = tmp_path / "usb"
    src.mkdir()
    for s in ("20240930124937", STAMP):
        shutil.copy2(SUB1 / f"2306490032R{s}", src)
    (src / "R20990101000000").write_bytes(b"\x01" * 40)  # bad trailer
    pid = repo.patients.list()[0].id
    d = ImportDialog(data / "ecg_app.db", data, pid)
    qtbot.addWidget(d)
    d.detect([tmp_path / "nothing", src])
    assert len(d.files) == 3
    with qtbot.waitSignal(d.done, timeout=120000):
        d.start_import()
    d.wait()
    r = d.result
    assert r.imported == ["2306490032R20240930124937"]
    assert r.skipped == [f"2306490032R{STAMP}"]  # already migrated from vendor
    assert len(r.errors) == 1
    recs = repo.recordings.for_patient(pid)
    assert len(recs) == 2 and (data / recs[0].pcm_path).stat().st_size == 4297500


def test_vendor_migration_dialog(qtbot, small_vendor, tmp_path):
    d = VendorMigrationDialog(tmp_path / "new", small_vendor)
    qtbot.addWidget(d)
    d.merge.setText("bad")
    d.start_migration()
    assert d.worker is None and "Помилка" in d.status.text()
    d.merge.setText("2=1")
    with qtbot.waitSignal(d.done, timeout=120000):
        d.start_migration()
    d.wait()
    assert d.result.counts["recordings_new"] == 1
    assert Repository(connect(tmp_path / "new" / "ecg_app.db")).patients.list()[0].name == "Grygoriev"
