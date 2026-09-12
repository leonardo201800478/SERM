"""Tema visual moderno do SERM V2.

A identidade arcade permanece na paleta de acentos e nos indicadores de estado,
mas a interface usa tipografia de sistema, superfícies suaves, cantos arredondados
e contraste controlado para priorizar conteúdo e legibilidade.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


MODERN_FONT_CANDIDATES = (
    "Segoe UI",
    "Inter",
    "Noto Sans",
    "Roboto",
    "Arial",
)

RETRO_ARCADE_THEME = """
/* ================================================================
   SERM V2 — MODERN ARCADE / DARK
   ================================================================ */
QWidget {
    background: #080d17;
    color: #d9e2ef;
    font-family: "{font_family}";
    font-size: 9pt;
}

QMainWindow, QWidget#centralWidget, QStackedWidget#pageStack {
    background: #080d17;
    border: 0;
}

QLabel {
    color: #cbd6e5;
    background: transparent;
}

QLabel[role="title"] {
    color: #e8eef7;
    font-size: 16pt;
    font-weight: 700;
    padding: 2px 0 4px 0;
}

QLabel[role="section"] {
    color: #8fd3e6;
    font-size: 10pt;
    font-weight: 600;
    padding: 2px 0;
}

QLabel#navigationBrand {
    color: #e8edf5;
    font-size: 22pt;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 3px 0 0 0;
}

QLabel#navigationVersion {
    color: #6eb6c9;
    font-size: 7pt;
    font-weight: 600;
    padding-bottom: 5px;
}

QFrame#navigationSidebar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #0d1421,stop:1 #0a101b);
    border: 1px solid #1d2a3e;
    border-radius: 10px;
}

QListWidget#navigationList {
    background: transparent;
    border: 0;
    outline: none;
    padding: 4px;
}

QListWidget#navigationList::item {
    color: #9eacbf;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 7px 9px;
    min-height: 26px;
    font-size: 9pt;
    font-weight: 500;
}

QListWidget#navigationList::item:hover {
    color: #e8f2f8;
    background: #111c2b;
    border-color: #22354a;
}

QListWidget#navigationList::item:selected {
    color: #f1f7fb;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #18293b,stop:1 #172238);
    border-color: #2e5264;
    border-left: 3px solid #68c5d9;
}

QLabel#navigationFooter {
    color: #64758b;
    font-size: 6.5pt;
    padding: 6px 4px 2px 4px;
}

QTabWidget::pane {
    background: #0c1320;
    border: 1px solid #1d2a3e;
    border-radius: 9px;
    top: -1px;
}

QTabBar {
    background: transparent;
}

QTabBar::tab {
    background: #0d1421;
    color: #8493a7;
    border: 1px solid #1d2a3e;
    border-bottom: 0;
    border-radius: 7px 7px 0 0;
    padding: 6px 12px 7px 12px;
    min-width: 64px;
    margin-right: 3px;
    font-weight: 500;
}

QTabBar::tab:hover {
    color: #dce8f2;
    background: #121d2c;
    border-top: 2px solid #5bb9ce;
}

QTabBar::tab:selected {
    color: #eef7fb;
    background: #101b2a;
    border-top: 2px solid #72c7da;
}

QGroupBox {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0d1523,stop:1 #0b1320);
    border: 1px solid #203047;
    border-radius: 9px;
    margin-top: 10px;
    padding: 11px 9px 8px 9px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 5px;
    color: #9bc9d5;
    background: #080d17;
    font-weight: 600;
}

QFrame#panel {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #101a29,stop:1 #0c1523);
    border: 1px solid #203047;
    border-radius: 9px;
}

QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #172334,stop:1 #111b2a);
    color: #d7e1ed;
    border: 1px solid #2b3d55;
    border-radius: 7px;
    padding: 5px 10px;
    min-height: 20px;
    min-width: 82px;
    font-weight: 500;
}

QPushButton:hover {
    background: #1a2b3e;
    color: #f2f7fa;
    border-color: #4d8ca0;
}

QPushButton:pressed {
    background: #172738;
    border-color: #70c2d4;
}

QPushButton:disabled {
    color: #566579;
    background: #0c131f;
    border-color: #19263a;
}

QPushButton[role="primary"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1b3040,stop:1 #233044);
    color: #e5f2f6;
    border: 1px solid #4c93a5;
}

QPushButton[role="primary"]:hover {
    background: #254054;
    border-color: #79c9da;
}

QPushButton[role="folder"] {
    background: #122631;
    color: #ccecf2;
    border: 1px solid #477e8d;
    min-width: 96px;
}

QPushButton[role="danger"] {
    background: #28171e;
    color: #e6a4af;
    border-color: #70414d;
}

QLineEdit, QComboBox, QSpinBox {
    background: #09111d;
    color: #dce6f0;
    border: 1px solid #293a51;
    border-radius: 7px;
    padding: 5px 8px;
    min-height: 20px;
    selection-background-color: #29475a;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #63b8cc;
}

QCheckBox, QRadioButton {
    spacing: 6px;
    color: #c7d2df;
    font-weight: 500;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #40536b;
    border-radius: 4px;
    background: #0a111d;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #63b9cc;
    border-color: #78c9d9;
}

QRadioButton::indicator {
    border-radius: 7px;
}

QListWidget, QTreeWidget, QTableWidget {
    background: #0a111c;
    color: #ced9e6;
    border: 1px solid #1e2d43;
    border-radius: 8px;
    alternate-background-color: #0d1725;
    selection-background-color: #193347;
    selection-color: #eef7fb;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 5px 7px;
    border-bottom: 1px solid #172336;
    min-height: 22px;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background: #122033;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background: #193347;
    color: #e9f5f8;
    border-left: 3px solid #67bfd2;
}

QHeaderView::section {
    background: #111c2a;
    color: #9bc9d5;
    border: 0;
    border-right: 1px solid #24364c;
    border-bottom: 1px solid #2b455a;
    padding: 6px 7px;
    font-weight: 600;
}

QProgressBar {
    background: #0a111c;
    border: 1px solid #27394f;
    border-radius: 5px;
    text-align: center;
    color: #dce8f0;
    min-height: 8px;
    max-height: 8px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4b9fb3,stop:1 #72c6d7);
    border-radius: 4px;
    margin: 0;
}

QScrollArea {
    background: #080d17;
    border: 0;
}

QScrollBar:vertical {
    background: #0a111b;
    width: 9px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #2a3c53;
    min-height: 24px;
    border: 1px solid #38506a;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4e8799;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: #080d17;
    border: 0;
}

QPlainTextEdit#logConsole {
    background: #070d13;
    color: #9fd0b0;
    border: 1px solid #274334;
    border-radius: 8px;
    selection-background-color: #183529;
    selection-color: #d6f4df;
    font-family: "{font_family}";
    font-size: 8pt;
    padding: 5px;
}

QStatusBar {
    background: #09111b;
    color: #8fbea1;
    border-top: 1px solid #203a30;
    font-family: "{font_family}";
    font-size: 7pt;
}

QToolTip {
    background: #111d2b;
    color: #e1edf3;
    border: 1px solid #4c8798;
    padding: 5px;
    border-radius: 5px;
    font-family: "{font_family}";
}

QSplitter::handle {
    background: #1a293c;
}

QSplitter::handle:hover {
    background: #4e899a;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}
"""


def resolve_modern_font() -> str:
    """Seleciona uma fonte de interface limpa realmente instalada."""
    installed = {family.casefold(): family for family in QFontDatabase.families()}
    for candidate in MODERN_FONT_CANDIDATES:
        family = installed.get(candidate.casefold())
        if family:
            return family
    return "Sans Serif"


def apply_retro_arcade_theme(app: QApplication) -> str:
    """Aplica o visual moderno e retorna a família tipográfica selecionada."""
    app.setStyle("Fusion")
    font_family = resolve_modern_font()
    app.setFont(QFont(font_family, 9))
    app.setStyleSheet(RETRO_ARCADE_THEME.replace("{font_family}", font_family))
    return font_family


# Compatibilidade com consumidores antigos que importam o nome anterior.
PIXEL_FONT_CANDIDATES = MODERN_FONT_CANDIDATES
resolve_pixel_font = resolve_modern_font


__all__ = [
    "MODERN_FONT_CANDIDATES",
    "PIXEL_FONT_CANDIDATES",
    "RETRO_ARCADE_THEME",
    "apply_retro_arcade_theme",
    "resolve_modern_font",
    "resolve_pixel_font",
]
