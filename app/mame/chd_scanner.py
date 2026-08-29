"""Leitura do tamanho real de arquivos CHD a partir do disco.

O -listxml do MAME não informa o tamanho de CHDs (ao contrário das ROMs,
que trazem o atributo ``size``) — o tamanho de um CHD só existe fisicamente
no arquivo, já que depende da compressão. Por isso o "Tamanho estimado" da
aba de Filtragem não conseguia contabilizar CHDs: essa informação
simplesmente não vem do listxml.

Este módulo resolve isso escaneando o(s) diretório(s) configurados em
``rompath`` no mame.ini — a mesma pasta onde o MAME procura os arquivos
das máquinas — seguindo a convenção padrão do MAME:

    <rompath>/<nome_da_maquina>/<nome_do_disco>.chd

Cada arquivo encontrado tem seu tamanho real lido via ``Path.stat()`` e
devolvido para quem chamar persistir no banco (ver
``DatabaseService.update_chd_sizes``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


def scan_chd_sizes(rompaths: Iterable[str]) -> dict[tuple[str, str], int]:
    """Varre os rompaths procurando arquivos .chd e retorna seus tamanhos reais.

    Args:
        rompaths: caminhos configurados em mame.ini -> rompath (pode ser
            mais de um; o MAME procura em todos, nessa ordem).

    Returns:
        Dicionário {(nome_da_maquina, nome_do_disco): tamanho_em_bytes}.
        Se o mesmo (máquina, disco) aparecer em mais de um rompath, o
        primeiro encontrado vence (mesma prioridade que o MAME usa).
    """
    result: dict[tuple[str, str], int] = {}

    for rp in rompaths:
        root = Path(rp)
        if not root.is_dir():
            logger.warning(f"rompath não é um diretório válido, ignorando: {rp}")
            continue

        try:
            machine_dirs = [d for d in root.iterdir() if d.is_dir()]
        except OSError as e:
            logger.warning(f"Não foi possível listar {root}: {e}")
            continue

        for machine_dir in machine_dirs:
            machine_name = machine_dir.name
            try:
                chd_files = list(machine_dir.glob("*.chd"))
            except OSError as e:
                logger.warning(f"Não foi possível listar {machine_dir}: {e}")
                continue

            for chd_file in chd_files:
                disk_name = chd_file.stem
                key = (machine_name, disk_name)
                if key in result:
                    continue  # já encontrado em um rompath de prioridade maior
                try:
                    result[key] = chd_file.stat().st_size
                except OSError as e:
                    logger.warning(f"Não foi possível ler o tamanho de {chd_file}: {e}")

    logger.info(f"Scanner de CHD: {len(result)} arquivo(s) .chd encontrados em {list(rompaths)}")
    return result
