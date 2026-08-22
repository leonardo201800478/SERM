"""Card reutilizável para apresentar o estado de um emulador."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

from app.gui.design.colors import COLORS


class EmulatorStatusCard(QFrame):
    """Apresenta nome, estado, versão e executável de um emulador."""

    def __init__(self, name: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("emulatorCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        self.icon = QLabel("●")
        self.icon.setFixedWidth(20)
        layout.addWidget(self.icon, alignment=Qt.AlignTop)

        text = QVBoxLayout()
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-weight: 700;")
        self.status_label = QLabel("Não configurado")
        self.path_label = QLabel("")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.version_label = QLabel("")
        text.addWidget(self.name_label)
        text.addWidget(self.status_label)
        text.addWidget(self.version_label)
        text.addWidget(self.path_label)
        layout.addLayout(text, 1)

    def set_state(self, state: str, version: str | None, path: Path | None) -> None:
        """Atualiza estado visual e informações detectadas."""
        styles = {
            "ok": ("#2e7d32", "Detectado"),
            "warning": ("#ed6c02", "Executável não respondeu"),
            "missing": ("#9e9e9e", "Não configurado"),
        }
        color, text = styles.get(state, (COLORS.get("error", "#c62828"), "Indisponível"))
        self.icon.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.version_label.setText(f"Versão: {version}" if version else "Versão: não detectada")
        self.path_label.setText(f"Executável: {path}" if path else "Executável: não configurado")
