"""Paleta semântica única da interface.

As abas não devem definir cores de estado localmente; use os valores deste módulo.
"""

from __future__ import annotations


class Colors:
    """Cores semânticas usadas por widgets e estados da aplicação."""

    BG = "#12161d"
    SURFACE = "#1b212b"
    SURFACE_ALT = "#232b36"
    BORDER = "#384352"
    TEXT = "#e8edf3"
    MUTED = "#9aa7b5"
    PRIMARY = "#3b82f6"
    PRIMARY_HOVER = "#2563eb"
    SUCCESS = "#22c55e"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"
    INFO = "#38bdf8"
    DISABLED = "#667085"

    @classmethod
    def state(cls, state: str) -> str:
        """Retorna a cor semântica de um estado conhecido."""
        return {
            "success": cls.SUCCESS,
            "valid": cls.SUCCESS,
            "warning": cls.WARNING,
            "invalid": cls.ERROR,
            "error": cls.ERROR,
            "missing": cls.ERROR,
            "info": cls.INFO,
            "disabled": cls.DISABLED,
        }.get(str(state).lower(), cls.TEXT)
