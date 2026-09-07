"""Tema visual Retro Arcade do SERM V2.

A camada visual prioriza tipografia pixel/terminal, geometria quadrada, alto
contraste e uma paleta neon inspirada em arcades dos anos 80/90.
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
   SERM V2 — RETRO ARCADE / PIXEL ART
   ================================================================ */
QWidget {
    background-color: #080b18;
    color: #e8f7ff;
    font-family: "{font_family}";
    font-size: 10pt;
}

QMainWindow, QWidget#centralWidget, QStackedWidget#pageStack {
    background-color: #080b18;
    border: 0;
}

QLabel {
    color: #d9eaff;
    background: transparent;
}

QLabel[role="title"] {
    color: #fff6a8;
    font-size: 20pt;
    font-weight: 900;
    padding: 4px 0 9px 0;
}

QLabel[role="section"] {
    color: #ff4fd8;
    font-size: 11pt;
    font-weight: 900;
    padding: 4px 0;
}

QLabel#navigationBrand {
    color: #fff36b;
    font-size: 23pt;
    font-weight: 900;
    letter-spacing: 2px;
    padding: 6px 0 1px 0;
}

QLabel#navigationVersion {
    color: #35e9ff;
    font-size: 8pt;
    font-weight: 900;
    padding-bottom: 7px;
}

QFrame#navigationSidebar {
    background: #0d1024;
    border: 2px solid #343b69;
    border-radius: 0px;
}

QListWidget#navigationList {
    background: #080b18;
    border: 0px;
    outline: none;
    padding: 4px;
}

QListWidget#navigationList::item {
    color: #a7b5d8;
    background: #0d1024;
    border: 1px solid #202746;
    border-radius: 0px;
    padding: 8px 10px;
    min-height: 30px;
    font-size: 10pt;
    font-weight: 900;
}

QListWidget#navigationList::item:hover {
    color: #ffffff;
    background: #171c39;
    border: 2px solid #35e9ff;
}

QListWidget#navigationList::item:selected {
    color: #080b18;
    background: #fff36b;
    border: 2px solid #ff4fd8;
    border-left: 6px solid #35e9ff;
}

QLabel#navigationFooter {
    color: #66749d;
    font-size: 7pt;
    padding: 8px 5px 3px 5px;
}

QTabWidget::pane {
    background: #0d1024;
    border: 2px solid #343b69;
    border-top: 3px solid #ff4fd8;
}

QTabBar {
    background: #080b18;
}

QTabBar::tab {
    background: #10152d;
    color: #8999c4;
    border: 2px solid #252d50;
    border-bottom: 0px;
    border-radius: 0px;
    padding: 8px 18px 9px 18px;
    min-width: 82px;
    margin-right: 2px;
    font-weight: 900;
}

QTabBar::tab:hover {
    color: #ffffff;
    background: #171c39;
    border-top: 3px solid #35e9ff;
}

QTabBar::tab:selected {
    color: #fff36b;
    background: #171c39;
    border-top: 4px solid #ff4fd8;
}

QGroupBox {
    background: #0d1024;
    border: 2px solid #343b69;
    border-radius: 0px;
    margin-top: 15px;
    padding: 17px 12px 12px 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 1px 8px;
    color: #fff36b;
    background: #080b18;
    font-weight: 900;
}

QFrame#panel {
    background: #10152d;
    border: 2px solid #30395f;
    border-radius: 0px;
}

QPushButton {
    background: #151a35;
    color: #eaf7ff;
    border: 2px solid #53618f;
    border-radius: 0px;
    padding: 8px 14px;
    min-height: 22px;
    min-width: 118px;
    font-weight: 900;
}

QPushButton:hover {
    background: #1b2448;
    color: #ffffff;
    border-color: #35e9ff;
}

QPushButton:pressed {
    background: #392047;
    border-color: #ff4fd8;
}

QPushButton:disabled {
    color: #4e5879;
    background: #0d1020;
    border-color: #252b45;
}

QPushButton[role="primary"] {
    background: #34203e;
    color: #fff36b;
    border: 3px solid #ff4fd8;
}

QPushButton[role="primary"]:hover {
    background: #4b2558;
    border-color: #35e9ff;
}

QPushButton[role="folder"] {
    background: #102d36;
    color: #a9f9ff;
    border: 3px solid #35e9ff;
    min-width: 132px;
}

QPushButton[role="danger"] {
    background: #32151f;
    color: #ff718f;
    border-color: #ff3d68;
}

QLineEdit, QComboBox, QSpinBox {
    background: #070a16;
    color: #eaf7ff;
    border: 2px solid #3c4872;
    border-radius: 0px;
    padding: 8px 9px;
    selection-background-color: #ff4fd8;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 3px solid #35e9ff;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    color: #d9eaff;
    font-weight: 800;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 2px solid #53618f;
    border-radius: 0px;
    background: #080b18;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #fff36b;
    border-color: #ff4fd8;
}

QRadioButton::indicator {
    border-radius: 0px;
}

QListWidget, QTreeWidget, QTableWidget {
    background: #070a16;
    color: #d9eaff;
    border: 2px solid #30395f;
    border-radius: 0px;
    alternate-background-color: #0b1022;
    selection-background-color: #ff4fd8;
    selection-color: #ffffff;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #171d35;
    min-height: 24px;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background: #121a34;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background: #4a2055;
    color: #fff36b;
    border-left: 4px solid #35e9ff;
}

QHeaderView::section {
    background: #151a35;
    color: #35e9ff;
    border: 0px;
    border-right: 2px solid #30395f;
    border-bottom: 2px solid #ff4fd8;
    padding: 7px 8px;
    font-weight: 900;
}

QProgressBar {
    background: #070a16;
    border: 2px solid #53618f;
    border-radius: 0px;
    text-align: center;
    color: #fff36b;
    min-height: 16px;
}

QProgressBar::chunk {
    background: #28d66f;
    margin: 1px;
    border-right: 2px solid #8affb3;
}

QScrollArea {
    background: #080b18;
    border: 0px;
}

QScrollBar:vertical {
    background: #080b18;
    width: 13px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #343b69;
    min-height: 28px;
    border: 2px solid #53618f;
    border-radius: 0px;
}

QScrollBar::handle:vertical:hover {
    background: #35e9ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: #080b18;
    border: 0px;
}

QPlainTextEdit#logConsole {
    background: #020a05;
    color: #78ff9d;
    border: 2px solid #2d7445;
    border-radius: 0px;
    selection-background-color: #174c2b;
    selection-color: #c9ffd7;
    font-family: "{font_family}";
    font-size: 9pt;
    padding: 7px;
}

QStatusBar {
    background: #070a16;
    color: #78ff9d;
    border-top: 2px solid #35e9ff;
    font-family: "{font_family}";
    font-size: 8pt;
}

QToolTip {
    background: #0b1022;
    color: #fff36b;
    border: 2px solid #35e9ff;
    padding: 6px;
    font-family: "{font_family}";
}

QSplitter::handle {
    background: #252d50;
}

QSplitter::handle:hover {
    background: #35e9ff;
}

QSplitter::handle:horizontal {
    width: 6px;
}

QSplitter::handle:vertical {
    height: 6px;
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
    app.setFont(QFont(font_family, 10))
    app.setStyleSheet(RETRO_ARCADE_THEME.replace("{font_family}", font_family))
    return font_family


__all__ = [
    "PIXEL_FONT_CANDIDATES",
    "RETRO_ARCADE_THEME",
    "apply_retro_arcade_theme",
    "resolve_pixel_font",
]
