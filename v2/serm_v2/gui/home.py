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

    def refresh_status(self) -> None:
        """Compatibility entry point preserved from the V1 Home contract."""
        self.refresh()

    def update_all_emulators(self) -> None:
        """Compatibility entry point for the V1 bulk-update action."""
        self.update_all()

    def install_emulator(self, emulator: str) -> None:
        """Compatibility entry point for installing one standalone emulator."""
        self.install(emulator)

    def clear_install_log(self) -> None:
        """Clear the Home installation diagnostic console."""
        self.log_view.clear()

    def open_official_site(self, key: str) -> None:
        """Open the official emulator repository used by the Home card."""
        import webbrowser

        url = self.SITES.get(key)
        if url:
            webbrowser.open(url)

    def _done(self, key: str, result, continuation=None) -> None:
        """Persist the installation root and integration executable separately."""
        paths = self._load_paths()
        installation = paths.get(key)
        if installation is None:
            installation = Path(result.executable).parent
            paths[key] = installation
        paths[f"{key}_exe"] = Path(result.executable).resolve()
        paths[f"{key}_version"] = str(result.version)
        self._save_paths(paths)
        self._append_log(
            f"SUCESSO | {self.LABELS[key]} | versão={result.version} | instalação={installation} | exe={result.executable}"
        )
        self.refresh()
        if continuation:
            continuation()


__all__ = ["HomePage"]
