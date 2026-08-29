"""Home V2 baseada nos componentes funcionais originais do SERM."""
from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .emulator_home import EmulatorHomePage


class HomePage(EmulatorHomePage):
    """Expose the complete emulator Home under the original V2 API."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)


__all__ = ["HomePage"]
