"""Ponto único de acesso ao componente de scan por sistema.

A implementação operacional permanece em ``scan_phase_page`` durante a
migração da V2. Este módulo fornece uma API pública estável para páginas
especializadas, evitando imports de classes privadas.
"""

from ..scan_phase_page import _SystemScanTab

SystemScanTab = _SystemScanTab

__all__ = ["SystemScanTab"]
