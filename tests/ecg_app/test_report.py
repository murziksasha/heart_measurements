import glob
import json
import shutil
from pathlib import Path

import pytest

from ecg_app.core.models import AnalysisResult
from ecg_app.report.json_model import parse_cloud_report, parse_result

ROOT = Path(__file__).resolve().parents[2]
SUB1 = ROOT / "Data" / "DATA" / "userfiles" / "subusr" / "1"
REPORTS = sorted(glob.glob(str(SUB1 / "report_*.json")))


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_four_real_reports():
    assert len(REPORTS) == 4


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: Path(p).name)
def test_parse_real_report(path):
    rep = parse_cloud_report(_load(path))
    assert rep.ok and rep.source == "cloud"
    assert rep.avg_hr and rep.min_hr <= rep.avg_hr <= rep.max_hr
    assert rep.beat_count > 0 and rep.total_s > 0
    assert rep.data_start and rep.data_end
    assert rep.total_s == pytest.approx((rep.data_end - rep.data_start).total_seconds(), abs=2)
    assert rep.diagnoses and all(d.label("uk") and d.label("en") for d in rep.diagnoses)
    assert {"13000", "13001"} <= {e.code for e in rep.events}
    assert rep.unknown_codes() == set()
    for e in rep.events:
        # positions are 250 Hz; eventTime matches startPos offset from data start
        assert (e.time - rep.data_start).total_seconds() == pytest.approx(e.start_pos / 250, abs=1.5)
        s0, s1 = e.sample_range()
        assert 0 <= s0 < s1 <= rep.total_s * 125
        assert "[" not in e.label("uk")
    mx = next(e for e in rep.events if e.code == "13000")
    assert mx.hr == rep.max_hr and mx.label("uk") == "Максимальна ЧСС" and mx.label("en") == "Maximum heart rate"


def test_specific_values():
    rep = parse_cloud_report(_load(SUB1 / "report_1_2306490032_20261004205450.json"))
    assert (rep.avg_hr, rep.max_hr, rep.min_hr, rep.beat_count) == (79, 112, 66, 11749)
    assert rep.counters["ventricularPermatureBeatCount"] == 3
    pvc = [e for e in rep.events if e.code == "10000"]
    assert pvc and pvc[0].label("uk") == "Шлуночкова екстрасистола"
    assert [d.code for d in rep.diagnoses]


def test_unknown_code_stays_visible():
    rep = parse_cloud_report({"code": 200, "data": {"allEventList": [
        {"eventCode": "19999", "eventName": "房颤", "eventTime": "2026-01-01 00:00:10", "startPos": "2500", "endPos": "5000"},
        {"eventCode": "18888", "eventName": "新事件", "startPos": "0", "endPos": "10"}],
        "diagnoseList": [{"code": "999", "diagnoseInfo": "Something new"}]}})
    assert rep.unknown_codes() == {"18888", "19999"}
    labels = {e.code: e.label("uk") for e in rep.events}
    assert labels["19999"] == "Фібриляція передсердь [19999]"
    assert labels["18888"] == "新事件 [18888]"
    assert rep.diagnoses[0].label("en") == "Something new [999]"
    assert rep.events[1].sample_range() == (1250, 2500)


def test_parse_result_local_same_model():
    rep = parse_result("local", _load(REPORTS[0]))
    assert rep.source == "local" and rep.events


# --- UI -------------------------------------------------------------------

pytest.importorskip("PySide6")
from ecg_app.ui.report_view import ReportView  # noqa: E402


def test_report_view_empty_and_filled(qtbot, tmp_path):
    v = ReportView(tmp_path)
    qtbot.addWidget(v)
    assert v.stack.currentIndex() == 0
    shutil.copy2(SUB1 / "Record_1_2306490032_20261004205450Report.pdf", tmp_path / "r.pdf")
    a = AnalysisResult(recording_id=1, source="cloud", payload=_load(SUB1 / "report_1_2306490032_20261004205450.json"),
                       pdf_path="r.pdf")
    v.set_results([a])
    assert v.stack.currentIndex() == 1
    assert "Хмара Viatom AI" in v.header.text() and "2026-10-05 04:24" in v.header.text()
    assert v.pdf_btn.isEnabled()
    n_all = v.events.rowCount()
    v.set_filter("10000")
    assert 0 < v.events.rowCount() < n_all
    assert all(e.code == "10000" for e in v.shown_events)
    v.set_filter(None)
    assert v.events.rowCount() == n_all
    v.set_results([])
    assert v.stack.currentIndex() == 0


def test_jump_to_event(qtbot, tmp_path):
    from ecg_app.db.migrations import connect
    from ecg_app.db.repository import Repository
    from ecg_app.importers.vendor_import import run_import
    from ecg_app.ui.main_window import MainWindow

    stamp = "20261004161900"
    vd = tmp_path / "vendor" / "DATA" / "userfiles" / "subusr" / "1"
    vd.mkdir(parents=True)
    shutil.copy2(ROOT / "Data" / "DATA" / "db_lepu_care_world.db", vd.parents[2])
    for n in (f"2306490032R{stamp}", f"report_1_2306490032_{stamp}.json", f"Record_1_2306490032_{stamp}Report.pdf"):
        shutil.copy2(SUB1 / n, vd)
    data = tmp_path / "data"
    run_import(tmp_path / "vendor", data)
    repo = Repository(connect(data / "ecg_app.db"))
    w = MainWindow(repo, data, data / "ecg_app.db")
    qtbot.addWidget(w)
    w.show()
    w.tabs.setCurrentWidget(w.report)
    rv = w.report
    row = next(i for i, e in enumerate(rv.shown_events) if e.code == "13000")  # max HR at 49577 (250 Hz)
    with qtbot.waitSignal(rv.jump) as sig:
        rv.events.cellDoubleClicked.emit(row, 0)
    assert sig.args == [24788, 25788]
    assert w.tabs.currentWidget() is w.viewer
    lo, hi = w.viewer.highlight.getRegion()
    assert w.viewer.highlight.isVisible()
    assert (lo, hi) == pytest.approx((24788 / 125, 25788 / 125))
    x0, x1 = w.viewer.visible_range()[0]
    assert x0 <= lo and hi <= x1
    repo.conn.close()
