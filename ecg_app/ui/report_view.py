"""Report tab: summary, findings, events (jump to ECG), PDF."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QListWidget, QPushButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..report.json_model import COUNTERS, Report, parse_result
from . import i18n
from .i18n import tr
from .models import fmt_duration

try:  # optional embedded PDF view
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    HAS_QTPDF = True
except ImportError:  # pragma: no cover
    HAS_QTPDF = False


def _hms(dt) -> str:
    return dt.strftime("%H:%M:%S") if dt else ""


class ReportView(QWidget):
    jump = Signal(int, int)  # PCM sample start, end

    def __init__(self, data_dir: Path, parent=None):
        super().__init__(parent)
        self.data_dir = Path(data_dir)
        self.results = []
        self.report: Report | None = None
        self.pdf_path: Path | None = None
        self.shown_events = []
        lay = QVBoxLayout(self)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)

        self.empty = QLabel(tr("no_results"))
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#777; font-size:14px;")
        self.stack.addWidget(self.empty)

        page = QWidget()
        pv = QVBoxLayout(page)
        top = QHBoxLayout()
        self.result_combo = QComboBox()
        self.result_combo.currentIndexChanged.connect(self._show_index)
        self.header = QLabel()
        self.header.setStyleSheet("font-weight:bold;")
        self.pdf_btn = QPushButton(tr("open_pdf"))
        self.pdf_btn.clicked.connect(self.open_pdf)
        top.addWidget(self.result_combo)
        top.addWidget(self.header, 1)
        top.addWidget(self.pdf_btn)
        pv.addLayout(top)

        self.inner = QTabWidget()
        pv.addWidget(self.inner, 1)
        main = QSplitter()
        left = QWidget()
        lv = QVBoxLayout(left)
        self.summary_box = QGroupBox(tr("summary"))
        sb = QVBoxLayout(self.summary_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.summary = QFormLayout(holder)
        self.summary.setVerticalSpacing(4)
        scroll.setWidget(holder)
        sb.addWidget(scroll)
        lv.addWidget(self.summary_box, 3)
        diag_box = QGroupBox(tr("diagnoses"))
        dv = QVBoxLayout(diag_box)
        self.diag_list = QListWidget()
        dv.addWidget(self.diag_list)
        lv.addWidget(diag_box, 1)
        main.addWidget(left)

        right = QGroupBox(tr("events"))
        rv = QVBoxLayout(right)
        fh = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(self._fill_events)
        fh.addWidget(self.filter)
        hint = QLabel(tr("jump_hint"))
        hint.setStyleSheet("color:#777;")
        fh.addWidget(hint, 1)
        rv.addLayout(fh)
        self.events = QTableWidget(0, 3)
        self.events.setHorizontalHeaderLabels([tr("event_type"), tr("event_time"), tr("hr")])
        self.events.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.events.verticalHeader().hide()
        self.events.setEditTriggers(QTableWidget.NoEditTriggers)
        self.events.setSelectionBehavior(QTableWidget.SelectRows)
        self.events.cellDoubleClicked.connect(self.jump_to_row)
        rv.addWidget(self.events)
        main.addWidget(right)
        main.setSizes([380, 620])
        self.inner.addTab(main, tr("summary"))

        self.pdf_doc = None
        self.pdf_buffer = None  # PDF is loaded from memory: no OS file handle (Windows locks open files)
        if HAS_QTPDF:
            self.pdf_doc = QPdfDocument(self)
            self.pdf_view = QPdfView()
            self.pdf_view.setDocument(self.pdf_doc)
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.inner.addTab(self.pdf_view, tr("pdf_tab"))
        self.stack.addWidget(page)
        self.set_results([])

    # data -----------------------------------------------------------------
    def set_results(self, results):
        self.results = list(results)
        self.result_combo.blockSignals(True)
        self.result_combo.clear()
        for i, a in enumerate(self.results, 1):
            self.result_combo.addItem(tr("result_n", i) + f" · {tr('source_' + a.source)}")
        self.result_combo.setVisible(len(self.results) > 1)
        self.result_combo.blockSignals(False)
        if not self.results:
            self.report = None
            self.stack.setCurrentIndex(0)
            return
        self.stack.setCurrentIndex(1)
        self._show_index(0)

    def _show_index(self, i):
        if not (0 <= i < len(self.results)):
            return
        a = self.results[i]
        self.report = rep = parse_result(a.source, a.payload)
        when = rep.report_time.strftime("%Y-%m-%d %H:%M") if rep.report_time else (a.created_at or "")
        self.header.setText(tr("result_header", tr("source_" + a.source), when))
        lang = i18n.language()
        while self.summary.rowCount():
            self.summary.removeRow(0)
        bpm = tr("bpm")
        rows = [
            (tr("analysed"), f"{fmt_duration(rep.valid_s)} / {fmt_duration(rep.total_s)}"),
            (tr("avg_hr"), f"{rep.avg_hr} {bpm}" if rep.avg_hr is not None else "—"),
            (tr("max_hr"), f"{rep.max_hr} {bpm}  ({_hms(rep.max_hr_time)})" if rep.max_hr else "—"),
            (tr("min_hr"), f"{rep.min_hr} {bpm}  ({_hms(rep.min_hr_time)})" if rep.min_hr else "—"),
            (tr("beats"), str(rep.beat_count)),
        ]
        for k, pair in COUNTERS.items():
            if k in rep.counters:
                rows.append((pair[0] if lang == "uk" else pair[1], str(rep.counters[k])))
        for label, val in rows:
            self.summary.addRow(label + ":", QLabel(val))
        self.diag_list.clear()
        self.diag_list.addItems([d.label(lang) for d in rep.diagnoses])

        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem(tr("all_types"), None)
        for code in rep.event_codes():
            ev = next(e for e in rep.events if e.code == code)
            self.filter.addItem(ev.label(lang), code)
        self.filter.blockSignals(False)
        self._fill_events()

        self.pdf_path = (self.data_dir / a.pdf_path) if a.pdf_path else None
        has_pdf = bool(self.pdf_path and self.pdf_path.exists())
        self.pdf_btn.setEnabled(has_pdf)
        self.pdf_btn.setToolTip("" if has_pdf else tr("no_pdf"))
        if self.pdf_doc is not None:
            self.pdf_doc.close()
            if has_pdf:
                self.pdf_view.setDocument(self.pdf_doc)
                self._load_pdf_from_memory(self.pdf_path)
            self.inner.setTabEnabled(1, has_pdf)

    def _load_pdf_from_memory(self, path: Path):
        buf = QBuffer(self)
        buf.setData(QByteArray(path.read_bytes()))
        buf.open(QBuffer.ReadOnly)
        self.pdf_doc.load(buf)
        if self.pdf_buffer is not None:
            self.pdf_buffer.close()
        self.pdf_buffer = buf

    def release_files(self):
        """Close the embedded PDF so the file can be moved/deleted (Windows locks open files)."""
        if self.pdf_doc is not None:
            self.pdf_view.setDocument(None)
            self.pdf_doc.close()
            if self.pdf_buffer is not None:
                self.pdf_buffer.close()
                self.pdf_buffer = None
        self.pdf_path = None
        self.set_results([])

    def pdf_is_open(self) -> bool:
        return self.pdf_doc is not None and self.pdf_doc.status() == QPdfDocument.Status.Ready

    def set_filter(self, code):
        self.filter.setCurrentIndex(max(0, self.filter.findData(code)))

    def _fill_events(self, *_):
        rep = self.report
        code = self.filter.currentData()
        self.shown_events = [e for e in (rep.events if rep else []) if code is None or e.code == code]
        lang = i18n.language()
        self.events.setRowCount(len(self.shown_events))
        for r, e in enumerate(self.shown_events):
            for c, text in enumerate((e.label(lang), _hms(e.time), "" if e.hr is None else str(e.hr))):
                it = QTableWidgetItem(text)
                if not e.known and c == 0:
                    it.setForeground(Qt.darkRed)
                self.events.setItem(r, c, it)

    # actions ----------------------------------------------------------------
    def jump_to_row(self, row, _col=0):
        if 0 <= row < len(self.shown_events):
            self.jump.emit(*self.shown_events[row].sample_range())

    def open_pdf(self):
        if self.pdf_path and self.pdf_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pdf_path)))
