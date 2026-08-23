"""Catálogo local dos cores instalados do RetroArch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig


class RetroArchCatalogTab(QWidget):
    """Lista cores RetroArch instalados e os separa do catálogo de jogos nativos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a sessão de catálogo de cores."""
        layout = QVBoxLayout(self)
        title = QLabel("Catálogo RetroArch")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        description = QLabel(
            "O RetroArch é tratado aqui como plataforma de cores. O catálogo não confunde cores com jogos: "
            "cada core representa um backend libretro instalado e pode atender diferentes sistemas."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#888;")
        layout.addWidget(description)

        group = QGroupBox("Cores instalados")
        group_layout = QVBoxLayout(group)
        self.count_label = QLabel()
        self.cores_list = QListWidget()
        group_layout.addWidget(self.count_label)
        group_layout.addWidget(self.cores_list, 1)
        layout.addWidget(group, 1)

        refresh = QPushButton("Atualizar catálogo")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)

    def refresh(self) -> None:
        """Varre apenas o diretório local de cores configurado."""
        self.config.load()
        self.cores_list.clear()
        cores_dir = self.config.get_emulator_path("retroarch", "cores")
        if not cores_dir:
            self.count_label.setText("Cores: diretório não configurado")
            return
        path = Path(cores_dir)
        if not path.is_dir():
            self.count_label.setText(f"Cores: diretório não encontrado — {path}")
            return
        cores = sorted(path.glob("*.dll"), key=lambda item: item.name.casefold())
        for core in cores:
            self.cores_list.addItem(core.stem)
        self.count_label.setText(f"Cores instalados: {len(cores)} | Diretório: {path}")


__all__ = ["RetroArchCatalogTab"]
