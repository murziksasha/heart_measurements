from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal


class Worker(QObject):
    """Runs fn(progress, cancelled) in a QThread. progress(i, n, text)."""

    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable):
        super().__init__()
        self.fn = fn
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            res = self.fn(lambda i, n, t: self.progress.emit(i, n, t), lambda: self._cancel)
        except Exception as e:  # report to UI thread
            self.failed.emit(f"{type(e).__name__}: {e}")
        else:
            self.finished.emit(res)


def start(worker: Worker, parent=None) -> QThread:
    th = QThread(parent)
    worker.moveToThread(th)
    th.started.connect(worker.run)
    worker.finished.connect(th.quit)
    worker.failed.connect(th.quit)
    th.start()
    return th
