"""Ajustes de composição da interface SERM V2.

Este módulo altera somente a apresentação dos widgets já existentes: barras de
progresso, divisórias ajustáveis e tipografia dos consoles. A lógica funcional
permanece nas páginas e serviços originais.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTreeWidget,
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
    for index in range(splitter.count()):
        splitter.setCollapsible(index, False)
    splitter.setSizes(sizes)
    splitter.setStyleSheet(SPLITTER_STYLE)


def _collect_emulator_cards(home) -> list[QWidget]:
    """Obtém os cartões dos emuladores visíveis e remove seus indicadores locais."""
    cards: list[QWidget] = []
    for key in getattr(home, "EMULATORS", ()):
        entry = home.cards.get(key)
        if not entry:
            continue
        card = entry[0].parentWidget()
        if card is not None and card not in cards:
            cards.append(card)
        old_progress = entry[3]
        if old_progress is None:
            continue
        old_progress.hide()
        card_layout = card.layout() if card is not None else None
        if card_layout is not None:
            card_layout.removeWidget(old_progress)
    return cards


def _build_arcade_splitter(cards: list[QWidget]) -> QSplitter:
    """Cria a divisória principal com as colunas de emuladores."""
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
    return outer


def _build_progress_row(page: QWidget) -> tuple[QProgressBar, QLabel, QWidget]:
    """Cria a linha de progresso e o rótulo para o painel de emuladores."""
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
    return progress, status_label, status_row


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
    cards = _collect_emulator_cards(home)
    if len(cards) != 4:
        return False
    frame = next((w for w in page.findChildren(QFrame) if w.layout() is not None), None)
    if frame is None:
        return False
    index = layout.indexOf(frame)
    if index < 0:
        return False
    layout.removeWidget(frame)
    splitter = _build_arcade_splitter(cards)
    container = QWidget(page)
    container.setObjectName("emulatorCardsContainer")
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.addWidget(splitter)
    layout.insertWidget(index, container, 1)
    frame.setParent(None)
    frame.deleteLater()
    progress, status_label, status_row = _build_progress_row(page)
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


def _set_compact_font(widget: QWidget, point_size: float) -> None:
    """Reduz tipografia sem alterar a família de fonte definida pelo tema."""
    font = QFont(widget.font())
    font.setPointSizeF(point_size)
    widget.setFont(font)


def _protect_text_widget(widget: QWidget, minimum_height: int = 25) -> None:
    """Garante espaço físico mínimo sem cortar o conteúdo textual."""
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    widget.setSizePolicy(policy)
    widget.setMinimumHeight(max(minimum_height, widget.sizeHint().height()))
    widget.setMaximumHeight(16777215)


def _protect_button(button: QPushButton) -> None:
    """Dimensiona botões pelo texto real, evitando clipping horizontal e vertical."""
    button.ensurePolished()
    hint = button.sizeHint()
    # Margem adicional para o padding do stylesheet, DPI/escala do Windows e
    # pequenas diferenças de métrica entre as fontes Qt.
    button.setMinimumWidth(max(hint.width() + 18, 120))
    button.setMinimumHeight(max(hint.height() + 4, 28))
    button.setMaximumHeight(16777215)
    policy = button.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
    policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
    button.setSizePolicy(policy)
    button.adjustSize()


def _refine_arcade_studio(window) -> bool:
    """Compacta o Arcade Studio sem impor dimensões que possam cortar texto."""
    studio = getattr(window, "arcade_studio_tab", None)
    if studio is None or studio.property("layout_refined"):
        return False
    page_layout = studio.layout()
    if page_layout is None:
        return False
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(4)
    for child in studio.findChildren(QWidget):
        _set_compact_font(child, 9.0)
    title = studio.findChild(QLabel, "", options=Qt.FindChildOption.FindDirectChildrenOnly)
    if title is not None:
        _set_compact_font(title, 14.0)
        title.setMinimumHeight(26)
        title.setMaximumHeight(40)
    intro = page_layout.itemAt(1).widget() if page_layout.count() > 1 else None
    if isinstance(intro, QLabel):
        intro.setMinimumHeight(max(20, intro.sizeHint().height()))
        intro.setMaximumHeight(60)
        intro.setWordWrap(True)
    tabs = getattr(studio, "tabs", None)
    if isinstance(tabs, QTabWidget):
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(False)
        tabs.setMinimumHeight(30)
        tabs.setMaximumHeight(16777215)
        tabs.tabBar().setMinimumHeight(28)
        tabs.tabBar().setMaximumHeight(40)
        _set_compact_font(tabs, 9.0)
    catalog = tabs.widget(0) if isinstance(tabs, QTabWidget) else None
    if catalog is None:
        return False
    catalog_layout = catalog.layout()
    if catalog_layout is not None:
        catalog_layout.setContentsMargins(2, 2, 2, 2)
        catalog_layout.setSpacing(4)
    source_box = catalog.findChild(QGroupBox, "", options=Qt.FindChildOption.FindDirectChildrenOnly)
    if source_box is not None:
        source_box.setMaximumHeight(16777215)
        source_box.setMinimumHeight(0)
        source_layout = source_box.layout()
        if source_layout is not None:
            source_layout.setContentsMargins(7, 5, 7, 5)
            source_layout.setVerticalSpacing(4)
            source_layout.setHorizontalSpacing(8)
    for edit in catalog.findChildren(QLineEdit):
        _protect_text_widget(edit, 25)
        edit.setMinimumWidth(max(edit.minimumSizeHint().width(), 180))
        edit.setToolTip(edit.text())
    for button in catalog.findChildren(QPushButton):
        _protect_button(button)
    progress = getattr(studio, "load_progress", None)
    if isinstance(progress, QProgressBar):
        progress.setMinimumHeight(12)
        progress.setMaximumHeight(18)
    for label_name in ("scan_info", "comparison_status", "catalog_details"):
        label = getattr(studio, label_name, None)
        if isinstance(label, QLabel):
            label.setMinimumHeight(max(18, label.sizeHint().height()))
            label.setMaximumHeight(80)
            label.setWordWrap(True)
    table = getattr(studio, "catalog_table", None)
    if isinstance(table, QTableWidget):
        table.verticalHeader().setDefaultSectionSize(21)
        table.verticalHeader().setMinimumSectionSize(20)
        table.verticalHeader().setMinimumWidth(38)
        table.horizontalHeader().setMinimumHeight(25)
        header = table.horizontalHeader()
        for column in (0, 1, 3, 4, 5, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setAlternatingRowColors(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    tree = getattr(studio, "rom_tree", None)
    if isinstance(tree, QTreeWidget):
        tree.header().setMinimumHeight(25)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        tree.setUniformRowHeights(True)
        tree.setIndentation(16)
        tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    splitters = catalog.findChildren(QSplitter)
    if splitters:
        main_splitter = splitters[0]
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setStretchFactor(0, 58)
        main_splitter.setStretchFactor(1, 42)
        def _set_studio_split_sizes() -> None:
            height = main_splitter.height()
            if height > 0:
                main_splitter.setSizes([max(260, int(height * 0.58)), max(180, int(height * 0.42))])
        QTimer.singleShot(0, _set_studio_split_sizes)
    if title is not None:
        title.setObjectName("arcadeStudioTitle")
    studio.setProperty("layout_refined", True)
    return True


def apply_ui_refinement(window) -> dict[str, bool]:
    """Aplica a segunda camada visual sem alterar serviços ou lógica funcional."""
    for widget in window.findChildren(QProgressBar):
        widget.setMaximumHeight(max(widget.maximumHeight(), 18))
    home = getattr(window, "home_section", None)
    arcade_studio = _refine_arcade_studio(window)
    if home is None:
        return {"arcade": False, "retroarch": False, "arcade_studio": arcade_studio}
    arcade = _replace_arcade_cards(home)
    retroarch = _refine_retroarch_splitter(home)
    for console in window.findChildren(type(home.log_view)):
        console.setStyleSheet("")
        console.setObjectName("logConsole")
    return {"arcade": arcade, "retroarch": retroarch, "arcade_studio": arcade_studio}


__all__ = ["XP_PROGRESS_STYLE", "apply_ui_refinement"]
