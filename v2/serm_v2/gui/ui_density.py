"""Sistema de densidade visual compacto da GUI SERM V2.

A densidade é aplicada como uma camada sobre o tema (escuro ou claro),
centralizando medidas de tipografia, controles, espaçamentos e cards.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


COMPACT_DENSITY = """
/* ================================================================
   SERM V2 — COMPACT DENSITY / SCREEN REAL ESTATE
   ================================================================ */
QWidget { font-size: 9pt; }

QLabel[role="title"] {
    font-size: 16pt;
    padding: 2px 0 5px 0;
}

QLabel[role="section"] {
    font-size: 10pt;
    padding: 2px 0;
}

QPushButton {
    padding: 5px 10px;
    min-height: 20px;
    min-width: 88px;
}

QPushButton[role="primary"] { min-height: 22px; }
QPushButton[role="folder"] { min-width: 100px; }

QLineEdit, QComboBox, QSpinBox {
    padding: 5px 7px;
    min-height: 20px;
}

QCheckBox, QRadioButton { spacing: 5px; }

QCheckBox::indicator, QRadioButton::indicator {
    width: 12px;
    height: 12px;
}

QGroupBox {
    margin-top: 10px;
    padding: 12px 9px 8px 9px;
}

QGroupBox::title { padding: 0 5px; }

QTabBar::tab {
    padding: 5px 11px 6px 11px;
    min-width: 64px;
}

QListWidget::item, QTreeWidget::item {
    padding: 4px 6px;
    min-height: 21px;
}

QHeaderView::section { padding: 5px 6px; }
QProgressBar { min-height: 13px; }
QScrollBar:vertical { width: 10px; }

/* Hubs: cards compactos, sem impor cores que conflitem com o tema. */
QFrame#configCard, QFrame#sourceCard, QFrame#systemCard {
    min-height: 104px;
}

QLabel#configCardNumber, QLabel#sourceCardNumber, QLabel#systemCardNumber {
    font-size: 8pt;
    font-weight: 900;
}

QLabel#configCardTitle, QLabel#sourceCardTitle, QLabel#systemCardTitle {
    font-size: 10pt;
    font-weight: 900;
}

QLabel#configCardDescription, QLabel#sourceCardDescription, QLabel#systemCardDescription {
    font-size: 8pt;
}

QFrame#sourceStatusBanner { min-height: 28px; }
"""


def apply_compact_density(app: QApplication) -> None:
    """Acrescenta a camada compacta ao stylesheet já aplicado pelo tema."""
    current = app.styleSheet() or ""
    app.setStyleSheet(f"{current}\n{COMPACT_DENSITY}")


__all__ = ["COMPACT_DENSITY", "apply_compact_density"]
