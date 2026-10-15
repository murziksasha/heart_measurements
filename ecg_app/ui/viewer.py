"""ECG viewer for long 125 Hz single-lead recordings (pyqtgraph)."""

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
MM_PER_S = 25.0
MM_PER_MV = 10.0
SETTING_TRUE = "viewer_true_proportions"
# Paper grid: 0.04 s / 0.1 mV (1 mm) and 0.2 s / 0.5 mV (5 mm) at 25 mm/s, 10 mm/mV.
X_LEVELS = [(1.0, 0), (0.2, 0), (0.04, 0)]
Y_LEVELS = [(0.5, 0), (0.1, 0)]


class SecondsAxis(pg.AxisItem):
    """Labels only whole seconds; finer levels draw grid lines only."""

    def tickStrings(self, values, scale, spacing):
        return [f"{v:.0f}" if abs(v - round(v)) < 1e-6 else "" for v in values]


class EcgViewer(QWidget):
    def __init__(self, mv_height_scale: float = 1.0, settings=None, parent=None):
        super().__init__(parent)
        self.scale = float(mv_height_scale or 1.0)
        self.settings = settings
        self.fs = er1.SAMPLE_RATE
        self.samples = np.zeros(0, dtype=np.int16)
        self.mv = np.zeros(0)
        self.start_s = 0.0
        self.width_s = WINDOW_S

        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.title = QLabel(tr("no_recording"))
        self.paper = QCheckBox(tr("paper_grid"))
        self.paper.setChecked(True)
        self.true_mode = QCheckBox(tr("true_proportions"))
        self.true_mode.setChecked(bool(settings.get(SETTING_TRUE, False)) if settings else False)
        top.addWidget(self.title, 1)
        top.addWidget(self.true_mode)
        top.addWidget(self.paper)
        v.addLayout(top)

        self.plot = pg.PlotWidget(axisItems={"bottom": SecondsAxis("bottom")})
        self.plot.setLabel("bottom", tr("time_s"))
        self.plot.setLabel("left", tr("mv"))
        self.curve = self.plot.plot([], [], pen=pg.mkPen("k", width=1))
        self.curve.setClipToView(True)
        self.curve.setDownsampling(auto=True, method="peak")
        self.vb = self.plot.getViewBox()
        self.vb.sigXRangeChanged.connect(self._sync_scroll)
        self.vb.sigResized.connect(self._relayout)
        self.highlight = pg.LinearRegionItem(movable=False, brush=pg.mkBrush(255, 200, 0, 90),
                                             pen=pg.mkPen(230, 150, 0))
        self.highlight.setZValue(-5)
        self.highlight.hide()
        self.plot.addItem(self.highlight)
        v.addWidget(self.plot, 1)

        self.scroll = QScrollBar(Qt.Horizontal)
        self.scroll.valueChanged.connect(self._scrolled)
        v.addWidget(self.scroll)
        self.paper.toggled.connect(self._apply_style)
        self.true_mode.toggled.connect(self._mode_changed)
        self._apply_style()

    # geometry -------------------------------------------------------------
    def px_per_mm(self) -> tuple[float, float]:
        return self.logicalDpiX() / 25.4, self.logicalDpiY() / 25.4

    def true_window(self) -> tuple[float, float]:
        """Visible (seconds, mV) for the viewbox size at 25 mm/s, 10 mm/mV."""
        r = self.vb.size()
        px, py = self.px_per_mm()
        return max(r.width(), 1) / (MM_PER_S * px), max(r.height(), 1) / (MM_PER_MV * py)

    def is_true(self) -> bool:
        return self.true_mode.isChecked()

    # data -----------------------------------------------------------------
    def load_samples(self, samples: np.ndarray, title: str = ""):
        self.samples = np.asarray(samples, dtype=np.int16)
        self.mv = er1.to_mv(self.samples) * self.scale
        self.curve.setData(np.arange(len(self.mv)) / self.fs, self.mv)
        self.highlight.hide()
        self.title.setText(title or tr("viewer"))
        self.show_window(0.0)

    def highlight_samples(self, start: int, end: int):
        """Highlight samples [start, end) and center the view on them."""
        t0, t1 = start / self.fs, max(end, start + 1) / self.fs
        self.highlight.setRegion((t0, t1))
        self.highlight.show()
        width = self.true_window()[0] if self.is_true() else self.width_s
        self.show_window(max(0.0, (t0 + t1) / 2 - width / 2), width)

    def load_pcm(self, path: Path, title: str = ""):
        self.load_samples(er1.load_pcm(path), title or Path(path).name)

    def duration_s(self) -> float:
        return len(self.samples) / self.fs

    def show_window(self, start_s: float, width_s: float | None = None):
        if self.is_true():
            width_s, height_mv = self.true_window()
        else:
            width_s = width_s or self.width_s
            height_mv = 4.0
            self.width_s = width_s
        self.start_s = max(0.0, start_s)
        self.plot.setXRange(self.start_s, self.start_s + width_s, padding=0)
        mid = 0.0
        if len(self.mv):
            seg = self.mv[int(self.start_s * self.fs): int((self.start_s + width_s) * self.fs)]
            if len(seg):
                mid = float(np.median(seg))
        self.plot.setYRange(mid - height_mv / 2, mid + height_mv / 2, padding=0)
        self._update_scroll(width_s)

    def visible_range(self):
        return self.vb.viewRange()

    def _update_scroll(self, width_s):
        self.scroll.blockSignals(True)
        self.scroll.setRange(0, max(0, int((self.duration_s() - width_s) * 10)))
        self.scroll.setPageStep(max(1, int(width_s * 10)))
        self.scroll.setValue(int(self.start_s * 10))
        self.scroll.blockSignals(False)

    def _scrolled(self, v):
        lo, hi = self.vb.viewRange()[0]
        self.show_window(v / 10.0, hi - lo)

    def _sync_scroll(self, *_):
        lo = self.vb.viewRange()[0][0]
        self.scroll.blockSignals(True)
        self.scroll.setValue(int(max(0, lo) * 10))
        self.scroll.blockSignals(False)

    def _relayout(self, *_):
        if self.is_true():
            self.show_window(self.start_s)

    def _mode_changed(self, on):
        if self.settings is not None:
            self.settings.set(SETTING_TRUE, bool(on))
        self._apply_style()
        self.show_window(self.start_s, WINDOW_S)

    # style ----------------------------------------------------------------
    def _apply_style(self):
        paper = self.paper.isChecked()
        self.plot.setBackground(PAPER_BG if paper else "w")
        ax_x, ax_y = self.plot.getAxis("bottom"), self.plot.getAxis("left")
        if paper:
            ax_x.setTickSpacing(levels=X_LEVELS)
            ax_y.setTickSpacing(levels=Y_LEVELS)
            self.plot.showGrid(x=True, y=True, alpha=0.6)
        else:
            ax_x.setTickSpacing(levels=[(1.0, 0)])
            ax_y.setTickSpacing()
            self.plot.showGrid(x=True, y=True, alpha=0.2)
        # true proportions: fixed scale, navigate with the scrollbar only
        self.vb.setMouseEnabled(x=not self.is_true(), y=False)
