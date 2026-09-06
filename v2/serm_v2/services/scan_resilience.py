"""Controle cooperativo de pausa/cancelamento dos scans V2."""
from __future__ import annotations

import threading

HEARTBEAT_SECONDS = 5.0


class ScanControl:
    """Estado thread-safe do ciclo de vida de um scan.

    Pausar nunca cancela o scan e nunca destrói o worker. O scanner bloqueia
    somente em pontos seguros e continua exatamente do mesmo checkpoint ao
    receber resume. Cancelar permanece uma operação distinta e definitiva.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._paused = False
        self._cancelled = False

    def pause(self) -> None:
        with self._condition:
            if not self._cancelled:
                self._paused = True
                self._condition.notify_all()

    def resume(self) -> None:
        with self._condition:
            if not self._cancelled:
                self._paused = False
                self._condition.notify_all()

    def cancel(self) -> None:
        with self._condition:
            self._cancelled = True
            self._paused = False
            self._condition.notify_all()

    @property
    def paused(self) -> bool:
        with self._condition:
            return self._paused

    @property
    def cancelled(self) -> bool:
        with self._condition:
            return self._cancelled

    def wait_if_paused(self) -> None:
        with self._condition:
            while self._paused and not self._cancelled:
                self._condition.wait()

    def checkpoint(self) -> None:
        self.wait_if_paused()
        if self.cancelled:
            raise RuntimeError("Operação cancelada.")
