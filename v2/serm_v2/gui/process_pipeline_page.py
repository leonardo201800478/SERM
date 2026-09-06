"""Pipeline visual do SERM V2 dividido em tres fases independentes.

A interface deixa explicita a fronteira entre:
1. auditoria completa contra o catalogo/DAT;
2. filtragem de um snapshot de scan ja persistido;
3. reconstrucao do resultado filtrado.

As implementacoes existentes sao reutilizadas para reduzir risco durante a
migracao da V2: o legado FilterProfilesPage permanece como editor de filtros,
enquanto esta pagina passa a organizar o fluxo por fase e por fonte.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .filter_profiles_resume_page import FilterProfilesPage
from .reconstruction_page import ReconstructionPage
from .scan_phase_page import ScanPhasePage


class PhaseHeader(QFrame):
    """Cabecalho compacto que explica a responsabilidade da fase."""

    def __init__(self, number: str, title: str, description: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("processPhaseHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        badge = QLabel(number)
        badge.setObjectName("processPhaseNumber")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(34)
        layout.addWidget(badge)
        text = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setProperty("role", "title")
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(description_label)
        layout.addLayout(text, 1)


class FilteringPhasePage(QWidget):
    """Fase 2: edicao/aplicacao dos filtros sobre scans persistidos."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(PhaseHeader(
            "2", "FILTRAGEM DE ROMS",
            "Selecione um resultado de scan completo, aplique o perfil de selecao "
            "e gere um novo arquivo filtrado. O scan original nunca e alterado.", self,
        ))
        self.tabs = QTabWidget()
        self.tabs.setObjectName("filterSystemTabs")
        # A implementacao de filtros V2 existente ja possui o catalogo MAME e os
        # controles especificos. Ela fica encapsulada nesta fase para nao misturar
        # a auditoria com a reconstrucao.
        self.mame = FilterProfilesPage(self)
        self.tabs.addTab(self.mame, "MAME")
        for label in ("No-Intro", "Redump", "WHLoader", "C64"):
            self.tabs.addTab(self._not_ready(label), label)
        layout.addWidget(self.tabs, 1)

    @staticmethod
    def _not_ready(system: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel(f"Filtragem {system}")
        title.setProperty("role", "title")
        layout.addWidget(title)
        message = QLabel(
            "Esta fonte ja possui catalogo/scan na V2, mas a etapa de filtragem "
            "especifica ainda nao esta habilitada. O SERM nao reutilizara o scan "
            "nem aplicara heuristicas ate que o filtro desse sistema esteja definido."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        layout.addStretch()
        return page


class ReconstructionPhasePage(QWidget):
    """Fase 3: consumo do arquivo filtrado e montagem no destino escolhido."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(PhaseHeader(
            "3", "RECONSTRUCAO DE ROMS",
            "Escolha um arquivo filtrado, defina o diretorio de destino e monte "
            "o set. Nenhum novo scan e executado nesta fase.", self,
        ))
        self.tabs = QTabWidget()
        self.tabs.setObjectName("reconstructionSystemTabs")
        for label in ("MAME", "No-Intro", "Redump", "WHLoader", "C64"):
            tab = ReconstructionPage(self)
            tab.source_label.setText(f"Fonte: {label} | aguardando arquivo filtrado")
            self.tabs.addTab(tab, label)
        layout.addWidget(self.tabs, 1)


class ProcessPipelinePage(QWidget):
    """Container das tres fases operacionais do SERM."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("processPipelineTabs")
        self.scan_page = ScanPhasePage(self)
        self.filter_page = FilteringPhasePage(self)
        self.reconstruction_page = ReconstructionPhasePage(self)
        self.tabs.addTab(self.scan_page, "1 — SCAN")
        self.tabs.addTab(self.filter_page, "2 — FILTRAGEM")
        self.tabs.addTab(self.reconstruction_page, "3 — RECONSTRUCAO")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        self.scan_page.refresh()
        self.filter_page.mame.refresh()
        for index in range(self.reconstruction_page.tabs.count()):
            widget = self.reconstruction_page.tabs.widget(index)
            if hasattr(widget, "refresh"):
                widget.refresh()


__all__ = ["ProcessPipelinePage", "FilteringPhasePage", "ReconstructionPhasePage"]
