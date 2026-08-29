"""Widgets especializados usados pela aba ScanRomsTab.

A aba original concentrava XML, perfis, diretórios, progresso, contadores
e árvore de resultados em uma única classe. Este pacote separa cada
responsabilidade em um widget próprio, para que ``ScanRomsTab`` atue
apenas como orquestradora (fiação de sinais, threads e integração com
banco/filtros/RomScanner).

Widgets:
    ScanControlWidget
        XML, perfil, origens, destino, workers e controles do scan.

    ScanSummaryWidget
        Progresso, contadores, status e perfil ativo.

    RomTreeWidget
        Árvore de máquinas/ROMs com origem física, CRC/SHA1, status e
        menu contextual de reparo.
"""

from .rom_tree_widget import RomTreeWidget
from .scan_control_widget import ScanControlWidget
from .scan_summary_widget import ScanSummaryWidget

__all__ = [
    "RomTreeWidget",
    "ScanControlWidget",
    "ScanSummaryWidget",
]
