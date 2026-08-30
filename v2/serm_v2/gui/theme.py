"""Sistema visual unificado do SERM V2 com estética arcade/pixel-art."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPlainTextEdit


# Paleta inspirada em arcades 16-bit, CRT e terminais de desenvolvimento.
# A segunda camada do tema privilegia hierarquia, densidade e leitura em 16:9.
PIXEL_THEME = """
QWidget {
    background-color: #1b1b1b;
    color: #e6e6e6;
    font-family: "Segoe UI";
    font-size: 10pt;
}

QMainWindow, QWidget#centralWidget {
    background-color: #1b1b1b;
}

QLabel {
    color: #dddddd;
}

QLabel[role="title"] {
    color: #ffffff;
    font-size: 20pt;
    font-weight: 900;
    padding: 2px 0 7px 0;
}

QLabel[role="section"] {
    color: #d13d78;
    font-size: 11pt;
    font-weight: 800;
    padding: 3px 0;
}

QTabWidget::pane {
    background-color: #242424;
    border: 1px solid #454545;
    border-top: 2px solid #9c2f60;
}

QTabBar {
    background-color: #171717;
}

QTabBar::tab {
    background-color: #202020;
    color: #a9a9a9;
    border: 1px solid #383838;
    border-bottom: none;
    padding: 8px 18px 9px 18px;
    min-width: 82px;
    margin-right: 2px;
}

QTabBar::tab:hover {
    background-color: #2a2a2a;
    color: #ffffff;
    border-top: 2px solid #00c8d7;
}

QTabBar::tab:selected {
    background-color: #292929;
    color: #ffffff;
    border-top: 2px solid #d13d78;
}

QGroupBox {
    background-color: #232323;
    border: 1px solid #4b4b4b;
    margin-top: 14px;
    padding: 12px 10px 9px 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    padding: 0 6px;
    color: #d13d78;
    background-color: #1b1b1b;
    font-weight: 900;
}

QFrame#panel {
    background-color: #232323;
    border: 1px solid #404040;
}

QFrame#panel:hover {
    border-color: #555555;
}

QPushButton {
    background-color: #303030;
    color: #eeeeee;
    border: 1px solid #555555;
    padding: 7px 13px;
    min-height: 19px;
    font-weight: 750;
}

QPushButton:hover {
    background-color: #393939;
    border-color: #00c8d7;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #252525;
    border-color: #d13d78;
    padding-top: 8px;
    padding-bottom: 6px;
}

QPushButton:disabled {
    color: #666666;
    border-color: #363636;
    background-color: #252525;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #151515;
    color: #e8e8e8;
    border: 1px solid #4d4d4d;
    padding: 6px 8px;
    selection-background-color: #79274b;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #00c8d7;
}

QComboBox QAbstractItemView {
    background-color: #202020;
    color: #eeeeee;
    border: 1px solid #00c8d7;
    selection-background-color: #79274b;
}

QCheckBox, QRadioButton {
    spacing: 7px;
    color: #d6d6d6;
}

QCheckBox:hover, QRadioButton:hover {
    color: #ffffff;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #666666;
    background-color: #151515;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #a72f5d;
    border-color: #d13d78;
}

QRadioButton::indicator {
    border-radius: 7px;
}

QListWidget, QTreeWidget, QTableWidget {
    background-color: #151515;
    color: #dedede;
    border: 1px solid #474747;
    alternate-background-color: #1c1c1c;
    selection-background-color: #54203a;
    selection-color: #ffffff;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 6px 6px;
    border-bottom: 1px solid #252525;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #282828;
}

QHeaderView::section {
    background-color: #242424;
    color: #bdbdbd;
    border: 0;
    border-right: 1px solid #3d3d3d;
    border-bottom: 1px solid #4d4d4d;
    padding: 6px 8px;
    font-weight: 800;
}

QProgressBar {
    background-color: #111111;
    border: 1px solid #494949;
    text-align: center;
    color: #f0f0f0;
    min-height: 13px;
}

QProgressBar::chunk {
    background-color: #00aebc;
    border-right: 1px solid #62f2fa;
}

QScrollArea {
    background-color: #1b1b1b;
    border: 0;
}

QScrollBar:vertical {
    background: #161616;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #4a4a4a;
    min-height: 28px;
    border: 1px solid #5e5e5e;
}

QScrollBar::handle:vertical:hover {
    background: #00aebc;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    border: none;
}

QPlainTextEdit#logConsole {
    background-color: #050b07;
    color: #8ee28e;
    border: 1px solid #315c3b;
    selection-background-color: #194827;
    selection-color: #caffca;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9pt;
    padding: 6px;
}

QStatusBar {
    background-color: #121212;
    color: #8ee28e;
    border-top: 1px solid #3c3c3c;
}

QToolTip {
    background-color: #111111;
    color: #ffffff;
    border: 1px solid #00c8d7;
    padding: 5px;
}
"""


def apply_theme(app: QApplication) -> None:
    """Aplica o tema gamer a toda a aplicação Qt."""
    app.setStyle("Fusion")
    app.setStyleSheet(PIXEL_THEME)


def refine_dashboard(root) -> dict[str, int]:
    """Refina a composição da janela após a construção dos widgets.

    Remove estilos locais de painéis que conflitariam com o tema global,
    identifica títulos/seções e aplica uma hierarquia visual consistente.
    """
    panels = 0
    titles = 0
    sections = 0

    for frame in root.findChildren(QFrame):
        # O tema global passa a controlar os painéis; isso elimina diferenças
        # de borda e espaçamento entre as telas legadas da V2.
        if frame.styleSheet():
            frame.setStyleSheet("")
        frame.setObjectName("panel")
        panels += 1

    for label in root.findChildren(QLabel):
        text = label.text().strip()
        if text in {"SERM V2", "SERM V2 — Home"} or text.startswith("SERM V2 —"):
            label.setStyleSheet("")
            label.setProperty("role", "title")
            label.style().unpolish(label)
            label.style().polish(label)
            titles += 1
        elif text in {"Log RetroArch", "Log detalhado da instalação"}:
            label.setStyleSheet("")
            label.setProperty("role", "section")
            label.style().unpolish(label)
            label.style().polish(label)
            sections += 1

    return {"panels": panels, "titles": titles, "sections": sections}


def normalize_log_widgets(root) -> int:
    """Padroniza todos os consoles QPlainTextEdit para o estilo de log do SERM."""
    widgets = root.findChildren(QPlainTextEdit)
    for widget in widgets:
        widget.setStyleSheet("")
        widget.setObjectName("logConsole")
        widget.setReadOnly(True)
        widget.setMaximumBlockCount(max(widget.maximumBlockCount(), 3000))
    return len(widgets)


__all__ = ["PIXEL_THEME", "apply_theme", "normalize_log_widgets", "refine_dashboard"]
