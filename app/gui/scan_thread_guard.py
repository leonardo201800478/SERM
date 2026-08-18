from __future__ import annotations
from PySide6.QtCore import QTimer

def _release(tab, worker):
    if worker is None:
        return
    if worker.isRunning():
        QTimer.singleShot(25, lambda: _release(tab, worker))
        return
    if getattr(tab, "worker", None) is worker:
        tab.worker = None
    worker.deleteLater()

def install():
    from app.gui.tabs.scan_roms_tab import ScanRomsTab
    if getattr(ScanRomsTab, "_thread_guard_installed", False):
        return
    original_finished = ScanRomsTab._on_worker_finished
    original_failed = ScanRomsTab._on_worker_failed
    def safe_finished(self, stats):
        worker = getattr(self, "worker", None)
        original_finished(self, stats)
        if worker is not None and getattr(self, "worker", None) is None:
            self.worker = worker
            QTimer.singleShot(0, lambda: _release(self, worker))
    def safe_failed(self, message):
        worker = getattr(self, "worker", None)
        original_failed(self, message)
        if worker is not None and getattr(self, "worker", None) is None:
            self.worker = worker
            QTimer.singleShot(0, lambda: _release(self, worker))
    ScanRomsTab._on_worker_finished = safe_finished
    ScanRomsTab._on_worker_failed = safe_failed
    ScanRomsTab._thread_guard_installed = True
