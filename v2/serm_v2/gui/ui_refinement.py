"""Ajustes de composição da interface SERM V2."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QTabWidget, QTableWidget, QTreeWidget, QVBoxLayout, QWidget, QGridLayout

XP_PROGRESS_STYLE = """
QProgressBar#xpProgress { background-color:#0b0b0b; border:1px solid #707070; border-radius:2px; padding:1px; text-align:center; color:#ffffff; min-height:18px; max-height:18px; }
QProgressBar#xpProgress::chunk { background-color:#55b82f; width:10px; margin:1px; border-right:1px solid #8de36a; }
QProgressBar#xpProgress[busy="true"] { color:#e8ffe0; }
"""


def _collect_emulator_cards(home) -> list[QWidget]:
    """Obtém os cards existentes e elimina o espaço reservado ao progresso individual."""
    cards = []
    for key in getattr(home, "EMULATORS", ()):
        entry = home.cards.get(key)
        if not entry:
            continue
        card = entry[0].parentWidget()
        if card is not None and card not in cards:
            cards.append(card)
            card.setMinimumHeight(0)
            card.setMaximumHeight(124)
            if card.layout() is not None:
                card.layout().setContentsMargins(8, 7, 8, 7)
                card.layout().setSpacing(3)
        old_progress = entry[3]
        if old_progress is not None:
            old_progress.hide()
            if card is not None and card.layout() is not None:
                card.layout().removeWidget(old_progress)
    return cards


def _build_arcade_grid(cards: list[QWidget]) -> QFrame:
    """Monta os quatro emuladores em uma grade 2x2 compacta."""
    frame = QFrame()
    frame.setObjectName("emulatorCardsFrame")
    grid = QGridLayout(frame)
    grid.setContentsMargins(6, 6, 6, 6)
    grid.setHorizontalSpacing(5)
    grid.setVerticalSpacing(5)
    for index, card in enumerate(cards):
        grid.addWidget(card, index // 2, index % 2)
    grid.setRowStretch(0, 1)
    grid.setRowStretch(1, 1)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    frame.setMaximumHeight(260)
    return frame


def _build_progress_row(page: QWidget):
    progress = QProgressBar(page)
    progress.setObjectName("xpProgress")
    progress.setProperty("busy", False)
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setFormat("Pronto")
    progress.setStyleSheet(XP_PROGRESS_STYLE)
    progress.setFixedHeight(18)
    row = QWidget(page)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel("Progresso dos emuladores")
    layout.addWidget(label)
    layout.addWidget(progress, 1)
    return progress, label, row


def _replace_arcade_cards(home) -> bool:
    tabs = getattr(home, "home_tabs", None)
    if tabs is None or tabs.count() == 0:
        return False
    page = tabs.widget(0)
    if page is None or page.property("arcade_refined"):
        return False
    layout = page.layout()
    cards = _collect_emulator_cards(home)
    if layout is None or len(cards) != 4:
        return False
    frame = next((w for w in page.findChildren(QFrame) if w.layout() is not None and w.objectName() != "emulatorCardsFrame"), None)
    if frame is None:
        return False
    index = layout.indexOf(frame)
    if index < 0:
        return False
    layout.removeWidget(frame)
    frame.setParent(None)
    frame.deleteLater()
    grid_frame = _build_arcade_grid(cards)
    layout.insertWidget(index, grid_frame)
    progress, label, row = _build_progress_row(page)
    layout.insertWidget(index + 1, row)
    home.home_progress = progress
    home.home_progress_label = label
    for key in home.EMULATORS:
        entry = home.cards[key]
        home.cards[key] = (entry[0], entry[1], entry[2], progress, entry[4])
    page.setProperty("arcade_refined", True)
    return True


def _refine_home_shell(home) -> bool:
    """Reduz o chrome da Home para priorizar a área operacional."""
    layout = home.layout()
    if layout is None or home.property("home_shell_refined"):
        return False
    layout.setContentsMargins(8, 6, 8, 4)
    layout.setSpacing(4)
    title = layout.itemAt(0).widget() if layout.count() > 0 else None
    if isinstance(title, QLabel):
        _set_compact_font(title, 16.0)
        title.setMinimumHeight(24)
        title.setMaximumHeight(30)
    tabs = getattr(home, "home_tabs", None)
    if isinstance(tabs, QTabWidget):
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setMinimumHeight(27)
        tabs.tabBar().setMaximumHeight(32)
    home.setProperty("home_shell_refined", True)
    return True


def _refine_home_space(home) -> bool:
    """Impede que logs e botões consumam espaço que deve permanecer disponível."""
    tabs = getattr(home, "home_tabs", None)
    if tabs is None or tabs.count() == 0:
        return False
    arcade = tabs.widget(0)
    if arcade is not None:
        for log in arcade.findChildren(QPlainTextEdit):
            log.setMinimumHeight(64)
            log.setMaximumHeight(94)
            log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for button in arcade.findChildren(QPushButton):
            button.setMaximumHeight(28)
            button.setMinimumHeight(25)
            button.setMaximumWidth(160)
            button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        frame = arcade.findChild(QFrame, "emulatorCardsFrame")
        if frame is not None:
            frame.setMaximumHeight(258)
    retro = tabs.widget(1)
    if retro is not None:
        for log in retro.findChildren(QPlainTextEdit):
            log.setMinimumHeight(64)
            log.setMaximumHeight(120)
            log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for button in retro.findChildren(QPushButton):
            button.setMaximumHeight(28)
            button.setMinimumHeight(25)
    dock = getattr(home.window(), "log_dock", None)
    if dock is not None:
        dock.setMinimumHeight(70)
        dock.setMaximumHeight(112)
    return True


def _refine_retroarch_layout(home) -> bool:
    """Mantém catálogo e log RetroArch no mesmo fluxo, priorizando a área útil do catálogo."""
    tabs = getattr(home, "home_tabs", None)
    if tabs is None or tabs.count() < 2:
        return False
    page = tabs.widget(1)
    if page is None or page.property("retro_layout_refined"):
        return False
    core = getattr(home, "core_list", None)
    log = getattr(home, "retro_log", None)
    if core is not None:
        core.setMinimumHeight(150)
        core.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    if log is not None:
        log.setMinimumHeight(90)
        log.setMaximumHeight(150)
        log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    page.setProperty("retro_layout_refined", True)
    return True


def _set_compact_font(widget: QWidget, point_size: float) -> None:
    font = QFont(widget.font())
    font.setPointSizeF(point_size)
    widget.setFont(font)


def _protect_text_widget(widget: QWidget, minimum_height: int = 25) -> None:
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    widget.setSizePolicy(policy)
    widget.setMinimumHeight(max(minimum_height, widget.sizeHint().height()))
    widget.setMaximumHeight(16777215)


def _protect_button(button: QPushButton) -> None:
    button.ensurePolished()
    hint = button.sizeHint()
    button.setMinimumWidth(max(hint.width() + 12, 96))
    button.setMinimumHeight(max(hint.height() + 2, 26))
    button.setMaximumHeight(32)
    policy = button.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
    policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
    button.setSizePolicy(policy)


def _refine_arcade_studio(window) -> bool:
    studio = getattr(window, "arcade_studio_tab", None)
    if studio is None or studio.property("layout_refined"):
        return False
    layout = studio.layout()
    if layout is None:
        return False
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    for child in studio.findChildren(QWidget):
        _set_compact_font(child, 9.0)
    title = studio.findChild(QLabel, "", options=Qt.FindChildOption.FindDirectChildrenOnly)
    if title is not None:
        _set_compact_font(title, 14.0)
        title.setMinimumHeight(26)
        title.setMaximumHeight(40)
    intro = layout.itemAt(1).widget() if layout.count() > 1 else None
    if isinstance(intro, QLabel):
        intro.setMinimumHeight(max(20, intro.sizeHint().height()))
        intro.setMaximumHeight(60)
        intro.setWordWrap(True)
    tabs = getattr(studio, "tabs", None)
    if not isinstance(tabs, QTabWidget):
        return False
    tabs.setDocumentMode(True)
    tabs.setUsesScrollButtons(False)
    tabs.setMinimumHeight(30)
    tabs.setMaximumHeight(16777215)
    tabs.tabBar().setMinimumHeight(28)
    tabs.tabBar().setMaximumHeight(40)
    _set_compact_font(tabs, 9.0)
    catalog = tabs.widget(0)
    if catalog is None:
        return False
    cl = catalog.layout()
    if cl is not None:
        cl.setContentsMargins(2, 2, 2, 2)
        cl.setSpacing(4)
    source = catalog.findChild(QGroupBox, "", options=Qt.FindChildOption.FindDirectChildrenOnly)
    if source is not None:
        source.setMinimumHeight(0)
        source.setMaximumHeight(16777215)
        sl = source.layout()
        if sl is not None:
            sl.setContentsMargins(7, 5, 7, 5)
            sl.setVerticalSpacing(4)
            sl.setHorizontalSpacing(8)
    for edit in catalog.findChildren(QLineEdit):
        _protect_text_widget(edit, 25)
        edit.setMinimumWidth(max(edit.minimumSizeHint().width(), 180))
    for button in catalog.findChildren(QPushButton):
        _protect_button(button)
    progress = getattr(studio, "load_progress", None)
    if isinstance(progress, QProgressBar):
        progress.setMinimumHeight(12)
        progress.setMaximumHeight(18)
    for name in ("scan_info", "comparison_status", "catalog_details"):
        label = getattr(studio, name, None)
        if isinstance(label, QLabel):
            label.setMinimumHeight(max(18, label.sizeHint().height()))
            label.setMaximumHeight(80)
            label.setWordWrap(True)
    table = getattr(studio, "catalog_table", None)
    if isinstance(table, QTableWidget):
        vh = table.verticalHeader()
        vh.setDefaultSectionSize(21)
        vh.setMinimumSectionSize(20)
        vh.setMinimumWidth(34)
        f = QFont(vh.font())
        f.setPointSizeF(7.5)
        vh.setFont(f)
        hh = table.horizontalHeader()
        hh.setMinimumHeight(25)
        for column in (0, 1, 3, 4, 5, 6, 7):
            hh.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    tree = getattr(studio, "rom_tree", None)
    if isinstance(tree, QTreeWidget):
        tree.header().setMinimumHeight(25)
        for column in (0, 1, 2, 3):
            tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        tree.setUniformRowHeights(True)
        tree.setIndentation(16)
        tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    if title is not None:
        title.setObjectName("arcadeStudioTitle")
    studio.setProperty("layout_refined", True)
    return True


def apply_ui_refinement(window) -> dict[str, bool]:
    for widget in window.findChildren(QProgressBar):
        widget.setMaximumHeight(max(widget.maximumHeight(), 18))
    home = getattr(window, "home_section", None)
    studio = _refine_arcade_studio(window)
    if home is None:
        return {"arcade": False, "retroarch": False, "arcade_studio": studio}
    _refine_home_shell(home)
    arcade = _replace_arcade_cards(home)
    retro = _refine_retroarch_layout(home)
    _refine_home_space(home)
    return {"arcade": arcade, "retroarch": retro, "arcade_studio": studio}


__all__ = ["XP_PROGRESS_STYLE", "apply_ui_refinement"]
