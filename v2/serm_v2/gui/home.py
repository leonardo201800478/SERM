"""Home V2 baseada nos componentes funcionais originais do SERM."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from .emulator_home import EmulatorHomePage


class HomePage(EmulatorHomePage):
    """Expose the complete emulator Home under the original V2 API."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def configure(self, key: str) -> None:
        """Select only the installation directory used by download/update."""
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Diretório de instalação — {self.LABELS[key]}",
            str(Path.home()),
        )
        if not selected:
            return
        paths = self._load_paths()
        paths[key] = Path(selected).resolve()
        self._save_paths(paths)
        self.manager.roots = paths
        self.refresh()


__all__ = ["HomePage"]
