#!/usr/bin/env python3
"""Offscreen screenshots of the UI with real data: ui_screenshots.py DATA_DIR OUT_DIR"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ecg_app.db.migrations import connect  # noqa: E402
from ecg_app.db.repository import Repository  # noqa: E402
from ecg_app.ui import i18n  # noqa: E402
from ecg_app.ui.main_window import MainWindow  # noqa: E402

data, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
repo = Repository(connect(data / "ecg_app.db"))
i18n.set_language(repo.settings.get("ui_language") or repo.settings.get("language"))
w = MainWindow(repo, data, data / "ecg_app.db")
w.resize(1400, 860)
w.show()
w.rec_view.selectRow(5)
app.processEvents()
w.viewer.show_window(60)
for _ in range(5):
    app.processEvents()
w.grab().save(str(out / "main_window.png"))
w.viewer.resize(1400, 500)
app.processEvents()
w.viewer.grab().save(str(out / "viewer.png"))
w.viewer.true_mode.blockSignals(True)  # don't persist the toggle
w.viewer.true_mode.setChecked(True)
w.viewer.true_mode.blockSignals(False)
w.viewer._apply_style()
w.viewer.show_window(60)
app.processEvents()
w.viewer.grab().save(str(out / "viewer_true.png"))
w.viewer.true_mode.setChecked(False)
w.viewer.show_window(60, 10)
w.viewer.paper.setChecked(False)
app.processEvents()
w.viewer.grab().save(str(out / "viewer_plain.png"))
w.tabs.setCurrentWidget(w.report)
w.report.events.selectRow(0)
app.processEvents()
w.grab().save(str(out / "report.png"))
w.report.jump_to_row(0)
app.processEvents()
w.grab().save(str(out / "report_jump.png"))
print("saved", sorted(p.name for p in out.glob("*.png")))
