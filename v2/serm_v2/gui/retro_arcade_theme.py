"""Tema visual Retro Arcade do SERM V2.

A camada visual prioriza tipografia pixel/terminal, geometria compacta,
alto contraste controlado e uma paleta neon inspirada em arcades clássicos.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


PIXEL_FONT_CANDIDATES = (
    "Pixel Operator",
    "Px437 IBM VGA8",
    "Perfect DOS VGA 437",
    "Terminus",
    "Unifont",
    "Cascadia Mono",
    "Consolas",
)


RETRO_ARCADE_THEME = """
/* ================================================================
   SERM V2 — RETRO ARCADE / COMPACT DARK
   ================================================================ */
QWidget {
    background-color: #070a14;
    color: #dce8f5;
    font-family: "{font_family}";
    font-size: 9pt;
}

QMainWindow, QWidget#centralWidget, QStackedWidget#pageStack {
    background-color: #070a14;
    border: 0;
}

QLabel {
    color: #cbd8e8;
    background: transparent;
}

QLabel[role="title"] {
    color: #f2e86b;
    font-size: 16pt;
    font-weight: 900;
    padding: 2px 0 4px 0;
}

QLabel[role="section"] {
    color: #ff4fbc;
    font-size: 10pt;
    font-weight: 900;
    padding: 2px 0;
}

QLabel#navigationBrand {
    color: #f2e86b;
    font-size: 22pt;
    font-weight: 900;
    letter-spacing: 2px;
    padding: 3px 0 0 0;
}

QLabel#navigationVersion {
    color: #39d7e8;
    font-size: 7pt;
    font-weight: 900;
    padding-bottom: 5px;
}

QFrame#navigationSidebar {
    background: #0b1020;
    border: 1px solid #27345d;
    border-radius: 0px;
}

QListWidget#navigationList {
    background: #070a14;
    border: 0;
    outline: none;
    padding: 3px;
}

QListWidget#navigationList::item {
    color: #9eacc4;
    background: #0b1020;
    border: 1px solid #1c2744;
    border-radius: 0px;
    padding: 6px 9px;
    min-height: 26px;
    font-size: 9pt;
    font-weight: 900;
}

QListWidget#navigationList::item:hover {
    color: #eefaff;
    background: #111a30;
    border: 1px solid #39d7e8;
}

QListWidget#navigationList::item:selected {
    color: #ffffff;
    background: #302044;
    border: 1px solid #b13c87;
    border-left: 3px solid #39d7e8;
}

QLabel#navigationFooter {
    color: #5f6e8b;
    font-size: 6.5pt;
    padding: 6px 4px 2px 4px;
}

QTabWidget::pane {
    background: #0b1020;
    border: 1px solid #27345d;
    border-top: 2px solid #c43c8c;
}

QTabBar {
    background: #070a14;
}

QTabBar::tab {
    background: #0d1325;
    color: #8291ad;
    border: 1px solid #1e2a49;
    border-bottom: 0;
    border-radius: 0;
    padding: 5px 11px 6px 11px;
    min-width: 64px;
    margin-right: 2px;
    font-weight: 900;
}

QTabBar::tab:hover {
    color: #ffffff;
    background: #121b32;
    border-top: 2px solid #39d7e8;
}

QTabBar::tab:selected {
    color: #f2e86b;
    background: #11182d;
    border-top: 2px solid #ff4fbc;
}

QGroupBox {
    background: #0b1020;
    border: 1px solid #27345d;
    border-radius: 0;
    margin-top: 10px;
    padding: 11px 8px 8px 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 5px;
    color: #f2e86b;
    background: #070a14;
    font-weight: 900;
}

QFrame#panel {
    background: #0e1528;
    border: 1px solid #27345d;
    border-radius: 0;
}

QPushButton {
    background: #111a2e;
    color: #dce8f5;
    border: 1px solid #445577;
    border-radius: 0;
    padding: 5px 10px;
    min-height: 20px;
    min-width: 88px;
    font-weight: 900;
}

QPushButton:hover {
    background: #17233d;
    color: #ffffff;
    border-color: #39d7e8;
}

QPushButton:pressed {
    background: #362040;
    border-color: #ff4fbc;
}

QPushButton:disabled {
    color: #4d5870;
    background: #0a0e19;
    border-color: #1d263b;
}

QPushButton[role="primary"] {
    background: #32203c;
    color: #f2e86b;
    border: 2px solid #c43c8c;
}

QPushButton[role="primary"]:hover {
    background: #42264e;
    border-color: #39d7e8;
}

QPushButton[role="folder"] {
    background: #0e2931;
    color: #b8f8ff;
    border: 2px solid #39d7e8;
    min-width: 100px;
}

QPushButton[role="danger"] {
    background: #30151f;
    color: #ff7f98;
    border-color: #a33b5a;
}

QLineEdit, QComboBox, QSpinBox {
    background: #060912;
    color: #e4eef9;
    border: 1px solid #354564;
    border-radius: 0;
    padding: 5px 7px;
    min-height: 20px;
    selection-background-color: #74335f;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #39d7e8;
}

QCheckBox, QRadioButton {
    spacing: 5px;
    color: #cbd8e8;
    font-weight: 800;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 12px;
    height: 12px;
    border: 1px solid #53617c;
    border-radius: 0;
    background: #080c16;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #f2e86b;
    border-color: #ff4fbc;
}

QRadioButton::indicator {
    border-radius: 0;
}

QListWidget, QTreeWidget, QTableWidget {
    background: #060912;
    color: #d3e0ed;
    border: 1px solid #27345d;
    border-radius: 0;
    alternate-background-color: #0a1120;
    selection-background-color: #71345f;
    selection-color: #ffffff;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 4px 6px;
    border-bottom: 1px solid #151e32;
    min-height: 21px;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background: #101a2d;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background: #42264d;
    color: #f2e86b;
    border-left: 3px solid #39d7e8;
}

QHeaderView::section {
    background: #111a2e;
    color: #39d7e8;
    border: 0;
    border-right: 1px solid #27345d;
    border-bottom: 2px solid #c43c8c;
    padding: 5px 6px;
    font-weight: 900;
}

QProgressBar {
    background: #060912;
    border: 1px solid #3c4a68;
    border-radius: 0;
    text-align: center;
    color: #f2e86b;
    min-height: 13px;
}

QProgressBar::chunk {
    background: #28c96b;
    margin: 1px;
    border-right: 1px solid #7af5a6;
}

QScrollArea {
    background: #070a14;
    border: 0;
}

QScrollBar:vertical {
    background: #080c17;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #2d3a5c;
    min-height: 24px;
    border: 1px solid #465676;
    border-radius: 0;
}

QScrollBar::handle:vertical:hover {
    background: #39d7e8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: #070a14;
    border: 0;
}

QPlainTextEdit#logConsole {
    background: #020805;
    color: #78ef9a;
    border: 1px solid #28613b;
    border-radius: 0;
    selection-background-color: #154127;
    selection-color: #caffd6;
    font-family: "{font_family}";
    font-size: 8pt;
    padding: 5px;
}

QStatusBar {
    background: #060912;
    color: #6ee58e;
    border-top: 1px solid #2a4860;
    font-family: "{font_family}";
    font-size: 7pt;
}

QToolTip {
    background: #0a1120;
    color: #f2e86b;
    border: 1px solid #39d7e8;
    padding: 4px;
    font-family: "{font_family}";
}

QSplitter::handle {
    background: #202d4b;
}

QSplitter::handle:hover {
    background: #39d7e8;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}
"""


def resolve_pixel_font() -> str:
    """Seleciona a melhor fonte pixel/terminal realmente instalada."""
    installed = {family.casefold(): family for family in QFontDatabase.families()}
    for candidate in PIXEL_FONT_CANDIDATES:
        family = installed.get(candidate.casefold())
        if family:
            return family
    return "Cascadia Mono"


def apply_retro_arcade_theme(app: QApplication) -> str:
    """Aplica o visual Retro Arcade e retorna a família tipográfica selecionada."""
    app.setStyle("Fusion")
    font_family = resolve_pixel_font()
    app.setFont(QFont(font_family, 9))
    app.setStyleSheet(RETRO_ARCADE_THEME.replace("{font_family}", font_family))
    return font_family


__all__ = [
    "PIXEL_FONT_CANDIDATES",
    "RETRO_ARCADE_THEME",
    "apply_retro_arcade_theme",
    "resolve_pixel_font",
]
