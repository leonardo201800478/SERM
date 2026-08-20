"""Busca rápida e determinística de CHDs durante o scan.

O scan físico não deve varrer o HDD procurando CHDs. Para cada disk do
LISTXML, existe somente um local lógico esperado:

    <rom_path>/<machine>/<disk>.chd

A existência é resolvida com operações diretas do filesystem. Nenhum ZIP,
7Z ou diretório de outra machine é pesquisado. A validação de SHA1 e
``chdman verify`` permanece na etapa de reconstrução/validação do CHD.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ChdPresence:
    """Resultado barato da localização de um CHD."""

    machine: str
    disk: str
    expected_path: Path
    exists: bool
    size: int | None = None


class FastChdScanner:
    """Resolve presença de CHDs sem busca global.

    A classe deliberadamente não calcula SHA1. Isso evita ler dezenas ou
    centenas de gigabytes durante a fase de descoberta. A reconstrução usa
    ``chdman info``/``verify`` somente para CHDs que realmente existem.
    """

    def __init__(self, rom_paths: Iterable[str | Path]) -> None:
        self.rom_paths = tuple(self._normalize_paths(rom_paths))

    @staticmethod
    def _normalize_paths(paths: Iterable[str | Path]) -> list[Path]:
        """Normaliza as origens e elimina diretórios duplicados."""
        result: list[Path] = []
        seen: set[str] = set()
        for value in paths:
            path = Path(value).expanduser()
            key = os.path.normcase(os.path.abspath(str(path)))
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
        return result

    @staticmethod
    def _filename(disk: str) -> str:
        """Converte o nome do disk para o nome físico esperado pelo MAME."""
        return disk if disk.lower().endswith(".chd") else f"{disk}.chd"

    def locate(self, machine: str, disk: str) -> ChdPresence:
        """Localiza um CHD somente no diretório da machine.

        A primeira origem contendo o arquivo é retornada. Se nenhuma origem
        possuir o arquivo, o resultado é ``exists=False`` sem qualquer
        tentativa de busca fora do caminho esperado.
        """
        filename = self._filename(disk)
        first_path = self.rom_paths[0] / machine / filename if self.rom_paths else Path(machine) / filename

        for base in self.rom_paths:
            candidate = base / machine / filename
            try:
                if candidate.is_file():
                    try:
                        size = candidate.stat().st_size
                    except OSError:
                        size = None
                    return ChdPresence(machine, disk, candidate, True, size)
            except OSError:
                continue

        return ChdPresence(machine, disk, first_path, False, None)

    def locate_many(self, requirements: Iterable[tuple[str, str]]) -> list[ChdPresence]:
        """Resolve vários CHDs com apenas testes diretos de existência."""
        return [self.locate(machine, disk) for machine, disk in requirements]
