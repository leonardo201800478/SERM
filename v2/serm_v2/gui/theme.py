"""Sistema visual unificado do SERM V2 com estética arcade/pixel-art."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QLayout,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
)

PIXEL_THEME = """
QWidget { background-color:#1b1b1b; color:#e6e6e6; font-family:"Segoe UI"; font-size:10pt; }
QMainWindow, QWidget#centralWidget { background-color:#1b1b1b; }
QLabel { color:#dddddd; }
QLabel[role="title"] { color:#fff; font-size:20pt; font-weight:900; padding:2px 0 7px 0; }
QLabel[role="section"] { color:#d13d78; font-size:11pt; font-weight:800; padding:3px 0; }

/* Navegação lateral principal */
QFrame#navigationSidebar {
    background:#151515;
    border:1px solid #343434;
    border-radius:10px;
}
QLabel#navigationBrand {
    color:#ffffff;
    font-size:24pt;
    font-weight:950;
    letter-spacing:2px;
    padding:4px 0 0 0;
}
QLabel#navigationVersion {
    color:#00c8d7;
    font-size:7.5pt;
    font-weight:800;
    letter-spacing:1px;
    padding-bottom:5px;
}
QListWidget#navigationList {
    background:transparent;
    border:0;
    outline:none;
    padding:2px;
}
QListWidget#navigationList::item {
    color:#a8a8a8;
    background:transparent;
    border:1px solid transparent;
    border-radius:7px;
    padding:7px 10px;
    min-height:30px;
    font-size:10.5pt;
    font-weight:700;
}
QListWidget#navigationList::item:hover {
    color:#ffffff;
    background:#242424;
    border:1px solid #3e3e3e;
}
QListWidget#navigationList::item:selected {
    color:#ffffff;
    background:#3a1d2d;
    border:1px solid #8d2857;
    border-left:3px solid #00c8d7;
}
QLabel#navigationFooter {
    color:#626262;
    font-size:7.5pt;
    padding:8px 5px 3px 5px;
}
QStackedWidget#pageStack { background:#1b1b1b; border:0; }

QTabWidget::pane { background:#242424; border:1px solid #454545; border-top:2px solid #9c2f60; }
QTabBar { background:#171717; }
QTabBar::tab { background:#202020; color:#a9a9a9; border:1px solid #383838; border-bottom:none; padding:8px 18px 9px 18px; min-width:82px; margin-right:2px; }
QTabBar::tab:hover { background:#2a2a2a; color:#fff; border-top:2px solid #00c8d7; }
QTabBar::tab:selected { background:#292929; color:#fff; border-top:3px solid #d13d78; }
QGroupBox { background:#202020; border:1px solid #4b4b4b; margin-top:14px; padding:16px 12px 12px 12px; }
QGroupBox::title { subcontrol-origin:margin; left:11px; padding:0 7px; color:#ff4f96; background:#1b1b1b; font-weight:900; }
QFrame#panel { background:#232323; border:1px solid #404040; }
QPushButton { background:#303030; color:#f2f2f2; border:1px solid #666; padding:7px 14px; min-height:20px; min-width:118px; font-weight:800; }
QPushButton:hover { background:#3b3b3b; border-color:#00d9e8; color:#fff; }
QPushButton:pressed { background:#54203a; border:2px solid #ff4f96; }
QPushButton:disabled { color:#666; border-color:#363636; background:#252525; }
QPushButton[role="primary"] { background:#5b2040; border:2px solid #d13d78; color:#fff; font-weight:900; }
QPushButton[role="primary"]:hover { background:#70284f; border-color:#00d9e8; }
QPushButton[role="folder"] { background:#15383b; border:2px solid #00c8d7; color:#bffcff; font-weight:900; min-width:132px; }
QPushButton[role="folder"]:hover { background:#1d5054; border-color:#62f2fa; }
QPushButton[role="danger"] { background:#3a2028; border-color:#9e3b59; }
QLineEdit, QComboBox, QSpinBox { background:#111; color:#f0f0f0; border:1px solid #555; padding:7px 9px; selection-background-color:#79274b; }
QLineEdit:read-only { background:#101718; color:#b9dadd; border:1px solid #49666a; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border:2px solid #00c8d7; }
QCheckBox, QRadioButton { spacing:7px; color:#d6d6d6; }
QCheckBox:hover, QRadioButton:hover { color:#fff; }
QCheckBox::indicator, QRadioButton::indicator { width:13px; height:13px; border:1px solid #666; background:#151515; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#a72f5d; border-color:#ff4f96; }
QRadioButton::indicator { border-radius:7px; }
QListWidget, QTreeWidget, QTableWidget { background:#101212; color:#dedede; border:1px solid #3f5759; alternate-background-color:#151a1a; selection-background-color:#8d2857; selection-color:#fff; outline:none; }
QListWidget::item, QTreeWidget::item { padding:5px 8px; border-bottom:1px solid #242d2d; min-height:24px; }
QListWidget::item:hover, QTreeWidget::item:hover { background:#203335; }
QListWidget::item:selected, QTreeWidget::item:selected { background:#8d2857; color:#fff; border-left:3px solid #00d9e8; }
QListWidget:focus { border:2px solid #00c8d7; }
QHeaderView::section { background:#242424; color:#bdbdbd; border:0; border-right:1px solid #3d3d3d; border-bottom:1px solid #4d4d4d; padding:6px 8px; font-weight:800; }
QProgressBar { background:#111; border:1px solid #555; text-align:center; color:#f0f0f0; min-height:13px; }
QProgressBar::chunk { background:#16a34a; border-right:2px solid #58e47a; margin:1px; }
QScrollArea { background:#1b1b1b; border:0; }
QScrollBar:vertical { background:#161616; width:12px; margin:0; }
QScrollBar::handle:vertical { background:#4a4a4a; min-height:28px; border:1px solid #5e5e5e; }
QScrollBar::handle:vertical:hover { background:#00aebc; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:none; border:none; }
QPlainTextEdit#logConsole { background:#020904; color:#8ee28e; border:1px solid #315c3b; selection-background-color:#194827; selection-color:#caffca; font-family:"Px437 IBM VGA8","Perfect DOS VGA 437","Fixedsys","Cascadia Mono","Consolas",monospace; font-size:9pt; padding:6px; }
QStatusBar { background:#121212; color:#8ee28e; border-top:1px solid #3c3c3c; font-family:"Px437 IBM VGA8","Fixedsys","Consolas",monospace; }
QToolTip { background:#111; color:#fff; border:1px solid #00c8d7; padding:5px; }
"""


def apply_theme(app: QApplication) -> None:
    """Aplica o tema gamer a toda a aplicação Qt."""
    app.setStyle("Fusion")
    app.setStyleSheet(PIXEL_THEME)


def _refresh_style(widget, property_name: str | None = None, value=None) -> None:
    if property_name is not None:
        widget.setProperty(property_name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _refine_frames(root) -> int:
    panels = 0
    for frame in root.findChildren(QFrame):
        if frame.objectName() == "navigationSidebar":
            continue
        if frame.styleSheet():
            frame.setStyleSheet("")
        frame.setObjectName("panel")
        panels += 1
    return panels


def _refine_labels(root) -> tuple[int, int]:
    titles = sections = 0
    for label in root.findChildren(QLabel):
        text = label.text().strip()
        if text in {"SERM V2", "SERM V2 — Home"} or text.startswith("SERM V2 —"):
            label.setStyleSheet("")
            _refresh_style(label, "role", "title")
            titles += 1
        elif text in {"Log RetroArch", "Log detalhado da instalação"}:
            label.setStyleSheet("")
            _refresh_style(label, "role", "section")
            sections += 1
    return titles, sections


def _refine_buttons(root) -> None:
    for button in root.findChildren(QPushButton):
        button.setMinimumHeight(max(button.minimumHeight(), 30))
        text = button.text().strip().casefold()
        role = None
        if any(token in text for token in ("selecionar pasta", "adicionar pasta", "selecionar diretório")):
            role = "folder"
        elif "remover selecionada" in text:
            role = "danger"
        elif "salvar diretórios" in text or "instalar selecionados" in text:
            role = "primary"
        if role:
            _refresh_style(button, "role", role)
        else:
            _refresh_style(button)


def _refine_lists(root) -> None:
    for widget in root.findChildren(QListWidget):
        if widget.objectName() == "navigationList":
            continue
        parent = widget.parentWidget()
        if parent and parent.__class__.__name__ == "PathListWidget":
            widget.setMinimumHeight(82)
            widget.setMaximumHeight(130)
        else:
            widget.setMinimumHeight(max(widget.minimumHeight(), 140))


def refine_dashboard(root) -> dict[str, int]:
    """Refina a composição das telas, incluindo a guia de diretórios."""
    root_layout = root.layout()
    if root_layout is not None:
        root_layout.setContentsMargins(10, 8, 10, 6)
        root_layout.setSpacing(6)
    for layout in root.findChildren(QLayout):
        layout.setSpacing(6)
    panels = _refine_frames(root)
    titles, sections = _refine_labels(root)
    _refine_buttons(root)
    _refine_lists(root)
    for widget in root.findChildren(QPlainTextEdit):
        widget.setMinimumHeight(max(widget.minimumHeight(), 150))
    for widget in root.findChildren(QProgressBar):
        widget.setMaximumHeight(20)
    for widget in root.findChildren(QTabWidget):
        widget.setDocumentMode(True)
        widget.setUsesScrollButtons(False)
    return {"panels": panels, "titles": titles, "sections": sections}


def normalize_log_widgets(root) -> int:
    """Padroniza todos os consoles QPlainTextEdit para o monitor de fósforo."""
    widgets = root.findChildren(QPlainTextEdit)
    for widget in widgets:
        widget.setStyleSheet("")
        widget.setObjectName("logConsole")
        widget.setReadOnly(True)
        widget.setMaximumBlockCount(max(widget.maximumBlockCount(), 3000))
    return len(widgets)


__all__ = ["PIXEL_THEME", "apply_theme", "normalize_log_widgets", "refine_dashboard"]
