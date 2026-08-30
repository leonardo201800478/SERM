"""Tema visual unificado do SERM V2 com estética gamer/pixel-art."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QPlainTextEdit


# Paleta inspirada em terminais CRT, arcades e interfaces de 16 bits.
# Mantemos contraste alto e poucos efeitos arredondados para preservar a leitura.
PIXEL_THEME = """
QWidget {
    background-color: #202020;
    color: #e8e8e8;
    font-family: "Segoe UI";
    font-size: 10pt;
}

QMainWindow, QWidget#centralWidget {
    background-color: #202020;
}

QLabel {
    color: #e8e8e8;
}

QLabel[role="title"] {
    color: #ffffff;
    font-size: 20pt;
    font-weight: 800;
}

QTabWidget::pane {
    background-color: #292929;
    border: 1px solid #454545;
    border-top: 2px solid #8f2b58;
}

QTabBar::tab {
    background-color: #242424;
    color: #bdbdbd;
    border: 1px solid #3d3d3d;
    border-bottom: none;
    padding: 8px 16px;
    min-width: 72px;
}

QTabBar::tab:hover {
    color: #ffffff;
    background-color: #303030;
}

QTabBar::tab:selected {
    background-color: #303030;
    color: #ffffff;
    border-top: 2px solid #d13d78;
}

QGroupBox {
    background-color: #262626;
    border: 1px solid #505050;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #d13d78;
    font-weight: 800;
}

QFrame {
    background-color: #252525;
    border: 1px solid #414141;
}

QPushButton {
    background-color: #303030;
    color: #ededed;
    border: 1px solid #5b5b5b;
    padding: 7px 12px;
    min-height: 18px;
    font-weight: 700;
}

QPushButton:hover {
    background-color: #393939;
    border-color: #00c8d7;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #252525;
    border-color: #d13d78;
}

QPushButton:disabled {
    color: #666666;
    border-color: #383838;
    background-color: #252525;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #171717;
    color: #e8e8e8;
    border: 1px solid #505050;
    padding: 6px 8px;
    selection-background-color: #8f2b58;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #00c8d7;
}

QComboBox QAbstractItemView {
    background-color: #202020;
    color: #eeeeee;
    border: 1px solid #00c8d7;
    selection-background-color: #8f2b58;
}

QCheckBox, QRadioButton {
    spacing: 7px;
    color: #dddddd;
}

QCheckBox:hover, QRadioButton:hover {
    color: #ffffff;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #6a6a6a;
    background-color: #161616;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #a72f5d;
    border-color: #d13d78;
}

QRadioButton::indicator {
    border-radius: 7px;
}

QListWidget, QTreeWidget, QTableWidget {
    background-color: #181818;
    color: #dedede;
    border: 1px solid #474747;
    alternate-background-color: #1e1e1e;
    selection-background-color: #54203a;
    selection-color: #ffffff;
}

QListWidget::item, QTreeWidget::item {
    padding: 5px 4px;
    border-bottom: 1px solid #282828;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #292929;
}

QProgressBar {
    background-color: #151515;
    border: 1px solid #4c4c4c;
    text-align: center;
    color: #f0f0f0;
    min-height: 13px;
}

QProgressBar::chunk {
    background-color: #00aebc;
    border-right: 1px solid #62f2fa;
}

QScrollArea {
    background-color: #202020;
    border: 1px solid #414141;
}

QPlainTextEdit {
    background-color: #050b07;
    color: #8ee28e;
    border: 1px solid #315c3b;
    selection-background-color: #194827;
    selection-color: #caffca;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9pt;
    line-spacing: 1px;
}

QStatusBar {
    background-color: #151515;
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


def normalize_log_widgets(root) -> int:
    """Padroniza todos os consoles QPlainTextEdit para o estilo de log do SERM."""
    widgets = root.findChildren(QPlainTextEdit)
    for widget in widgets:
        # Algumas telas antigas ainda possuem stylesheet local. Removê-lo
        # permite que o tema global controle todos os logs de forma uniforme.
        widget.setStyleSheet("")
        widget.setObjectName("logConsole")
        widget.setReadOnly(True)
        widget.setMaximumBlockCount(max(widget.maximumBlockCount(), 3000))
    return len(widgets)


__all__ = ["PIXEL_THEME", "apply_theme", "normalize_log_widgets"]
