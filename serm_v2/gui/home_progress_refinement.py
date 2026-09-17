"""Refinamento da barra de progresso agregada da Home V2."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QProgressBar


def _refresh_total_progress(home) -> None:
    """Representa a fila inteira, e não somente o download do core atual."""
    operation = getattr(home, "_operation_progress", None)
    if not isinstance(operation, QProgressBar):
        return

    worker = getattr(home, "worker", None)
    current = getattr(home, "_core_current_filename", None)
    queue = getattr(home, "_core_queue_with_channels", [])

    if worker is None:
        operation.hide()
        home._dashboard_queue_total = 0
        home._dashboard_queue_completed = 0
        return

    progress = getattr(home, "retro_progress", None)
    if current:
        remaining_including_current = len(queue) + 1
        total = int(getattr(home, "_dashboard_queue_total", 0) or 0)
        if total <= 0 or remaining_including_current > total:
            total = remaining_including_current
            home._dashboard_queue_total = total
            home._dashboard_queue_completed = 0

        completed = max(0, total - remaining_including_current)
        home._dashboard_queue_completed = completed

        fraction = 0.0
        if progress is not None and progress.maximum() > 0:
            fraction = max(0.0, min(1.0, progress.value() / progress.maximum()))

        value = int(((completed + fraction) / total) * 1000)
        operation.setRange(0, 1000)
        operation.setValue(max(0, min(1000, value)))
        operation.show()
        return

    # Operações RetroArch sem fila usam o progresso individual normalmente.
    if progress is not None and progress.maximum() > 0:
        operation.setRange(0, 1000)
        operation.setValue(int((progress.value() / progress.maximum()) * 1000))
    else:
        operation.setRange(0, 0)
    operation.show()


def refine_home_progress(home) -> bool:
    """Instala um atualizador leve para a barra agregada da Home."""
    if getattr(home, "_aggregate_progress_timer", None) is not None:
        return True

    home._dashboard_queue_total = 0
    home._dashboard_queue_completed = 0
    timer = QTimer(home)
    timer.setInterval(150)
    timer.timeout.connect(lambda: _refresh_total_progress(home))
    timer.start()
    home._aggregate_progress_timer = timer
    _refresh_total_progress(home)
    return True


__all__ = ["refine_home_progress"]
