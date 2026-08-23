"""Sessão Home dedicada ao RetroArch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig


class RetroArchHomeTab(QWidget):
    """Apresenta estado do RetroArch e acesso rápido às suas configurações."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a sessão Home do RetroArch."""
        layout = QVBoxLayout(self)
        title = QLabel("RetroArch")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        status = QGroupBox("Estado da instalação")
        form = QVBoxLayout(status)
        self.status_label = QLabel()
        self.path_label = QLabel()
        self.config_label = QLabel()
        self.cores_label = QLabel()
        for label in (self.status_label, self.path_label, self.config_label, self.cores_label):
            label.setWordWrap(True)
            form.addWidget(label)
        layout.addWidget(status)

        actions = QVBoxLayout()
        directories = QPushButton("Configurar diretórios")
        directories.clicked.connect(self.open_directories)
        actions.addWidget(directories)
        catalog = QPushButton("Abrir catálogo de cores")
        catalog.clicked.connect(self.open_catalog)
        actions.addWidget(catalog)
        settings = QPushButton("Configurações do RetroArch")
        settings.clicked.connect(self.open_settings)
        actions.addWidget(settings)
        layout.addLayout(actions)
        layout.addStretch()

    def refresh(self) -> None:
        """Atualiza o diagnóstico sem iniciar o RetroArch."""
        self.config.load()
        executable = self.config.retroarch_path
        root = self.config.retroarch_dir
        config_path = self.config.get_emulator_path("retroarch", "config") or root
        cores = self.config.get_emulator_path("retroarch", "cores")
        self.path_label.setText(f"Instalação: {root or 'não configurada'}")
        self.config_label.setText(f"Configuração: {config_path or 'não configurada'}")
        self.cores_label.setText(f"Cores: {cores or 'não configurado'}")
        if executable and Path(executable).is_file():
            self.status_label.setText(f"● Pronto | versão {self.config.retroarch_version or 'não detectada'}")
            self.status_label.setStyleSheet("color:#55d66b;font-weight:bold;")
        elif root:
            self.status_label.setText("● Diretório configurado; executável não localizado")
            self.status_label.setStyleSheet("color:#e5c454;font-weight:bold;")
        else:
            self.status_label.setText("● Não configurado")
            self.status_label.setStyleSheet("color:#999;font-weight:bold;")

    def _activate(self, attribute: str) -> None:
        """Seleciona uma aba principal da janela quando disponível."""
        window = self.parent_window
        widget = getattr(window, attribute, None)
        tab_widget = getattr(window, "tab_widget", None)
        if widget is not None and tab_widget is not None:
            tab_widget.setCurrentWidget(widget)

    def open_directories(self) -> None:
        """Abre a sessão central de diretórios com RetroArch selecionado."""
        self._activate("directories_tab")
        directories = getattr(self.parent_window, "directories_tab", None)
        if directories is not None and hasattr(directories, "select_emulator"):
            directories.select_emulator("retroarch")

    def open_catalog(self) -> None:
        """Abre a sessão de catálogo do RetroArch."""
        self._activate("retroarch_catalog_tab")

    def open_settings(self) -> None:
        """Abre a configuração do RetroArch no container de emuladores."""
        self._activate("emulator_settings_tab")
        settings = getattr(self.parent_window, "emulator_settings_tab", None)
        if settings is not None and hasattr(settings, "select_emulator"):
            settings.select_emulator("retroarch")


__all__ = ["RetroArchHomeTab"]
