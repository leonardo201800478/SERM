"""Proteção opcional para o ciclo de vida do worker de scan.

A aba Scan Roms possui versões em evolução e nem todas expõem os callbacks
históricos ``_on_worker_finished``/``_on_worker_failed``. O guard deve ser
inócuo quando esses callbacks não existem; instalar a proteção nunca pode
impedir a aplicação de iniciar.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QTimer

logger = logging.getLogger(__name__)


def _release(tab, worker):
    """Libera um QThread somente depois que ele realmente terminou."""
    if worker is None:
        return
    if worker.isRunning():
        QTimer.singleShot(25, lambda: _release(tab, worker))
        return
    if getattr(tab, "worker", None) is worker:
        tab.worker = None
    worker.deleteLater()


def install():
    """Instala o guard somente se a API esperada existir.

    A implementação anterior assumia que ``ScanRomsTab`` sempre possuía
    ``_on_worker_finished`` e ``_on_worker_failed``. Isso tornou a inicialização
    do aplicativo frágil quando a aba foi refatorada e esses callbacks deixaram
    de existir. A ausência deles significa apenas que não há nada para patchar.
    """
    from app.gui.tabs.scan_roms_tab import ScanRomsTab

    if getattr(ScanRomsTab, "_thread_guard_installed", False):
        return

    original_finished = getattr(ScanRomsTab, "_on_worker_finished", None)
    original_failed = getattr(ScanRomsTab, "_on_worker_failed", None)

    # A versão atual da ScanRomsTab não expõe esses callbacks. Nesse caso,
    # não instalar monkey-patches e, principalmente, não abortar o startup.
    if original_finished is None or original_failed is None:
        logger.debug(
            "Scan thread guard não instalado: callbacks legados não existem "
            "na ScanRomsTab atual."
        )
        ScanRomsTab._thread_guard_installed = True
        return

    def safe_finished(self, stats):
        """Executa o callback original e posterga a liberação do worker."""
        worker = getattr(self, "worker", None)
        original_finished(self, stats)
        if worker is not None and getattr(self, "worker", None) is None:
            self.worker = worker
            QTimer.singleShot(0, lambda: _release(self, worker))

    def safe_failed(self, message):
        """Executa o callback de erro e posterga a liberação do worker."""
        worker = getattr(self, "worker", None)
        original_failed(self, message)
        if worker is not None and getattr(self, "worker", None) is None:
            self.worker = worker
            QTimer.singleShot(0, lambda: _release(self, worker))

    ScanRomsTab._on_worker_finished = safe_finished
    ScanRomsTab._on_worker_failed = safe_failed
    ScanRomsTab._thread_guard_installed = True
