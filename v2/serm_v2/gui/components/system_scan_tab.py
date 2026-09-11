"""Componente reutilizável para execução de scans por sistema.

Mantém a implementação visual/operacional do scan fora das páginas de fase,
permitindo que MAME e outros sistemas utilizem o mesmo componente sem
acoplamento a classes privadas.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget


class SystemScanTab(QWidget):
    """Base reutilizável para uma aba de scan de um sistema.

    A implementação concreta pode estender esta classe e fornecer o widget
    de scan específico. O componente não impõe regras de negócio do sistema.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def set_scan_widget(self, widget: QWidget) -> None:
        """Define o widget operacional exibido pela aba."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
                child.deleteLater()
        self._layout.addWidget(widget)

    def refresh(self) -> None:
        """Atualiza o widget operacional quando suportado."""
        if self._layout.count() == 0:
            return
        widget = self._layout.itemAt(0).widget()
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()
