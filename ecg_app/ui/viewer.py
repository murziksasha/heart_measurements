"""ECG viewer for long 250 Hz single-lead recordings (pyqtgraph)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QScrollBar, QVBoxLayout, QWidget

from ..core import er1_format as er1
from .i18n import tr

WINDOW_S = 10.0
PAPER_BG = "#fff5f5"
GRID_MINOR = (255, 170, 170, 90)
GRID_MAJOR = (230, 90, 90, 160)
# Paper feel: grid at 0.04 s / 0.1 mV (1 mm) and 0.2 s / 0.5 mV (5 mm) at 25 mm/s, 10 mm/mV.


class EcgViewer(QWidget):
    def __init__(self, mv_height_scale: float = 1.0, parent=None):
        super().__init__(parent)
        self.scale = float(mv_height_scale or 1.0)
        self.fs = er1.SAMPLE_RATE
        self.samples = np.zeros(0, dtype=np.int16)
        self.mv = np.zeros(0)

        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.title = QLabel(tr("no_recording"))
        self.paper = QCheckBox(tr("paper_grid"))
        self.paper.setChecked(True)
        top.addWidget(self.title, 1)
        top.addWidget(self.paper)
        v.addLayout(top)

        self.plot = pg.PlotWidget()
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.setLabel("bottom", tr("time_s"))
        self.plot.setLabel("left", tr("mv"))
        self.curve = self.plot.plot([], [], pen=pg.mkPen("k", width=1))
        self.curve.setClipToView(True)
        self.curve.setDownsampling(auto=True, method="peak")
        self.plot.getViewBox().sigXRangeChanged.connect(self._sync_scroll)
        v.addWidget(self.plot, 1)

        self.scroll = QScrollBar(Qt.Horizontal)
        self.scroll.valueChanged.connect(self._scrolled)
        v.addWidget(self.scroll)
        self.paper.toggled.connect(self._apply_style)
        self._apply_style()

    # data -----------------------------------------------------------------
    def load_samples(self, samples: np.ndarray, title: str = ""):
        self.samples = np.asarray(samples, dtype=np.int16)
        self.mv = er1.to_mv(self.samples) * self.scale
        t = np.arange(len(self.mv)) / self.fs
        self.curve.setData(t, self.mv)
        self.title.setText(title or tr("viewer"))
        total = len(self.mv) / self.fs
        self.scroll.setRange(0, max(0, int((total - WINDOW_S) * 10)))
        self.scroll.setPageStep(int(WINDOW_S * 10))
        self.show_window(0.0)

    def load_pcm(self, path: Path, title: str = ""):
        self.load_samples(er1.load_pcm(path), title or Path(path).name)

    def duration_s(self) -> float:
        return len(self.samples) / self.fs

    def show_window(self, start_s: float, width_s: float = WINDOW_S):
        self.plot.setXRange(start_s, start_s + width_s, padding=0)
        if len(self.mv):
            seg = self.mv[int(start_s * self.fs): int((start_s + width_s) * self.fs)]
            if len(seg):
                mid = float(np.median(seg))
                self.plot.setYRange(mid - 2.0, mid + 2.0, padding=0)

    def _scrolled(self, v):
        lo, hi = self.plot.getViewBox().viewRange()[0]
        self.show_window(v / 10.0, hi - lo)

    def _sync_scroll(self, *_):
        lo = self.plot.getViewBox().viewRange()[0][0]
        self.scroll.blockSignals(True)
        self.scroll.setValue(int(max(0, lo) * 10))
        self.scroll.blockSignals(False)

    # style ----------------------------------------------------------------
    def _apply_style(self):
        paper = self.paper.isChecked()
        self.plot.setBackground(PAPER_BG if paper else "w")
        ax_x, ax_y = self.plot.getAxis("bottom"), self.plot.getAxis("left")
        if paper:
            ax_x.setTickSpacing(major=0.2, minor=0.04)  # 5 mm / 1 mm at 25 mm/s
            ax_y.setTickSpacing(major=0.5, minor=0.1)   # 5 mm / 1 mm at 10 mm/mV
            self.plot.showGrid(x=True, y=True, alpha=0.6)
        else:
            ax_x.setTickSpacing()
            ax_y.setTickSpacing()
            self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.getViewBox().setMouseEnabled(x=True, y=not paper)
