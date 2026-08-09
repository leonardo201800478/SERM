"""
Botão estilizado com cores personalizadas.
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt

class StyledButton(QPushButton):
    def __init__(self, text: str, color: str = "#0078D7", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self._darken(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken(color, 0.2)};
            }}
        """)

    def _darken(self, hex_color: str, factor: float = 0.1) -> str:
        """Escurece uma cor hexadecimal."""
        c = hex_color.lstrip('#')
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"