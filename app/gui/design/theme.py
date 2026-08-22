"""Estilo global da interface Qt.

O tema centraliza aparência para que as abas não acumulem estilos divergentes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.gui.design.colors import Colors
from app.gui.design.dimensions import BUTTON_HEIGHT, MIN_BUTTON_WIDTH


def apply_theme(app: QApplication) -> None:
    """Aplica o stylesheet global uma única vez na inicialização da aplicação."""
    app.setStyleSheet(f"""
        QWidget {{
            background: {Colors.BG};
            color: {Colors.TEXT};
            font-size: 10pt;
        }}
        QFrame#section {{
            background: {Colors.SURFACE};
            border: 1px solid {Colors.BORDER};
            border-radius: 7px;
        }}
        QLabel#sectionTitle {{
            font-weight: 700;
            color: {Colors.TEXT};
        }}
        QPushButton, QToolButton {{
            min-height: {BUTTON_HEIGHT}px;
            min-width: {MIN_BUTTON_WIDTH}px;
            padding: 4px 12px;
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            background: {Colors.SURFACE_ALT};
        }}
        QPushButton:hover, QToolButton:hover {{ background: {Colors.PRIMARY}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {Colors.PRIMARY_HOVER}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: {Colors.DISABLED}; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            min-height: 30px;
            border: 1px solid {Colors.BORDER};
            border-radius: 5px;
            padding: 2px 7px;
            background: {Colors.SURFACE};
        }}
        QProgressBar {{
            min-height: 18px;
            max-height: 20px;
            border: 1px solid {Colors.BORDER};
            border-radius: 5px;
            text-align: center;
            background: {Colors.SURFACE};
        }}
        QProgressBar::chunk {{ background: {Colors.PRIMARY}; border-radius: 4px; }}
        QTabWidget::pane {{ border: 1px solid {Colors.BORDER}; border-radius: 5px; }}
        QTabBar::tab {{ padding: 8px 14px; }}
        QTabBar::tab:selected {{ background: {Colors.PRIMARY}; border-radius: 4px; }}
        QPlainTextEdit, QTextEdit {{
            background: #0d1117;
            border: 1px solid {Colors.BORDER};
            border-radius: 5px;
        }}
    """)
