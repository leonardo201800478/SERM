"""Fachada de compatibilidade para o motor de reconstrução.

A implementação oficial está em :mod:`app.mame.reconstruction_engine`.
Este módulo permanece para preservar imports legados do projeto, mas não
mantém uma segunda implementação de reconstrução.
"""
from __future__ import annotations

from app.mame.reconstruction_engine import (
    ReconstructionEngine,
    ReconstructionMachine,
    ReconstructionResult,
    ReconstructionRom,
)


class ReconstructionService(ReconstructionEngine):
    """Compatibilidade legada; usa exatamente o mesmo motor do projeto."""



__all__ = [
    "ReconstructionEngine",
    "ReconstructionMachine",
    "ReconstructionResult",
    "ReconstructionRom",
    "ReconstructionService",
]
