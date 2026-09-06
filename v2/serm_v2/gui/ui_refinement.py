"""Ajustes de composição da interface SERM V2.

Este módulo altera somente a apresentação dos widgets já existentes: barras de
progresso, divisórias ajustáveis e tipografia dos consoles. A lógica funcional
permanece nas páginas e serviços originais.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

XP_PROGRESS_STYLE = """
QProgressBar#xpProgress {
    background-color: #0b0b0b;
    border: 1px solid #707070;
    border-radius: 2px;
    padding: 1px;
    text-align: center;
    color: #ffffff;
    min-height: 18px;
    max-height: 18px;
}
QProgressBar#xpProgress::chunk {
    background-color: #55b82f;
    width: 10px;
    margin: 1px;
    border-right: 1px solid #8de36a;
}
QProgressBar#xpProgress[busy="true"] { color: #e8ffe0; }
"""

SPLITTER_STYLE = """
QSplitter::handle { background-color: #353535; }
QSplitter::handle:hover { background-color: #00aebc; }
QSplitter::handle:horizontal { width: 5px; }
QSplitter::handle:vertical { height: 5px; }
"""


def _configure_splitter(splitter: QSplitter, object_name: str, sizes: list[int]) -> None:
    """Configura uma divisória gamer sem permitir colapso acidental dos painéis."""
    splitter.setObjectName(object_name)
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(5)
    splitter.setOpaqueResize(True)
    splitter.setStyleSheet(SPLITTER_STYLE)
    for index in range(splitter.count()):
        splitter.setCollapsible(index, False)
    splitter.setSizes(sizes)


def _replace_arcade_cards(home) -> bool:
    """Converte a grade fixa de emuladores em divisórias horizontal/vertical ajustáveis."""
    tabs = getattr(home, "home_tabs", None)
    if tabs is None or tabs.count() == 0:
        return False
    page = tabs.widget(0)
    if page is None or page.property("arcade_refined"):
        return False
    layout = page.layout()
    if layout is None:
        return False

    cards: list[QWidget] = []
    for key in getattr(home, "EMULATORS", ()):
        entry = home.cards.get(key)
        if not entry:
            continue
        card = entry[0].parentWidget()
        if card is not None and card not in cards:
            cards.append(card)
        old_progress = entry[3]
        if old_progress is not None:
            old_progress.hide()
            card_layout = card.layout() if card is not None else None
            if card_layout is not None:
                card_layout.removeWidget(old_progress)

    if len(cards) != 4:
        return False

    frame = next((w for w in page.findChildren(QFrame) if w.layout() is not None), None)
    if frame is None:
        return False
    index = layout.indexOf(frame)
    if index < 0:
        return False
    layout.removeWidget(frame)

    left = QSplitter(Qt.Orientation.Vertical)
    right = QSplitter(Qt.Orientation.Vertical)
    left.addWidget(cards[0])
    left.addWidget(cards[1])
    right.addWidget(cards[2])
    right.addWidget(cards[3])
    _configure_splitter(left, "splitterEmulatorsLeft", [1, 1])
    _configure_splitter(right, "splitterEmulatorsRight", [1, 1])

    outer = QSplitter(Qt.Orientation.Horizontal)
    outer.addWidget(left)
    outer.addWidget(right)
    _configure_splitter(outer, "splitterEmulatorsColumns", [1, 1])

    container = QWidget(page)
    container.setObjectName("emulatorCardsContainer")
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.addWidget(outer)
    layout.insertWidget(index, container, 1)

    frame.setParent(None)
    frame.deleteLater()

    progress = QProgressBar(page)
    progress.setObjectName("xpProgress")
    progress.setProperty("busy", False)
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setFormat("Pronto")
    progress.setStyleSheet(XP_PROGRESS_STYLE)
    progress.setMinimumHeight(18)
    progress.setMaximumHeight(18)

    status_row = QWidget(page)
    status_layout = QHBoxLayout(status_row)
    status_layout.setContentsMargins(0, 0, 0, 0)
    status_layout.setSpacing(8)
    status_label = QLabel("Progresso dos emuladores")
    status_label.setObjectName("homeProgressLabel")
    status_layout.addWidget(status_label)
    status_layout.addWidget(progress, 1)
    layout.insertWidget(index + 1, status_row)

    home.home_progress = progress
    home.home_progress_label = status_label
    for key in home.EMULATORS:
        entry = home.cards[key]
        home.cards[key] = (entry[0], entry[1], entry[2], progress, entry[4])

    page.setProperty("arcade_refined", True)
    return True


def _refine_retroarch_splitter(home) -> bool:
    """Cria uma divisória horizontal ajustável entre catálogo e log do RetroArch."""
    tabs = getattr(home, "home_tabs", None)
    if tabs is None or tabs.count() < 2:
        return False
    page = tabs.widget(1)
    if page is None or page.property("retro_splitter_refined"):
        return False
    layout = page.layout()
    core_list = getattr(home, "core_list", None)
    retro_log = getattr(home, "retro_log", None)
    if layout is None or core_list is None or retro_log is None:
        return False

    list_index = layout.indexOf(core_list)
    log_index = layout.indexOf(retro_log)
    if list_index < 0 or log_index < 0:
        return False

    log_label = None
    if log_index > 0:
        candidate = layout.itemAt(log_index - 1).widget()
        if isinstance(candidate, QLabel) and candidate.text().strip() == "Log RetroArch":
            log_label = candidate
            layout.removeWidget(candidate)

    layout.removeWidget(core_list)
    layout.removeWidget(retro_log)
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.addWidget(core_list)

    log_panel = QWidget(page)
    log_layout = QVBoxLayout(log_panel)
    log_layout.setContentsMargins(0, 0, 0, 0)
    if log_label is not None:
        log_layout.addWidget(log_label)
    log_layout.addWidget(retro_log, 1)
    splitter.addWidget(log_panel)
    _configure_splitter(splitter, "splitterRetroArchCatalogLog", [3, 2])
    layout.insertWidget(min(list_index, log_index), splitter, 1)

    retro_progress = getattr(home, "retro_progress", None)
    if retro_progress is not None:
        retro_progress.setObjectName("xpProgress")
        retro_progress.setStyleSheet(XP_PROGRESS_STYLE)
        retro_progress.setMinimumHeight(18)
        retro_progress.setMaximumHeight(18)

    page.setProperty("retro_splitter_refined", True)
    return True


def apply_ui_refinement(window) -> dict[str, bool]:
    """Aplica a segunda camada visual sem alterar serviços ou lógica funcional."""
    for widget in window.findChildren(QProgressBar):
        widget.setMaximumHeight(max(widget.maximumHeight(), 18))

    home = getattr(window, "home_section", None)
    if home is None:
        return {"arcade": False, "retroarch": False}

    arcade = _replace_arcade_cards(home)
    retroarch = _refine_retroarch_splitter(home)

    # Consoles mantêm o stylesheet global do tema de fósforo/pixel.
    for console in window.findChildren(type(home.log_view)):
        console.setStyleSheet("")
        console.setObjectName("logConsole")

    return {"arcade": arcade, "retroarch": retroarch}


__all__ = ["XP_PROGRESS_STYLE", "apply_ui_refinement"]
