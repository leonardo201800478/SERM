from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class MameIniCandidates:
    """
    Representa os possíveis mame.ini encontrados na instalação.
    """

    root: Path | None
    ini_folder: Path | None

    @property
    def has_multiple(self) -> bool:
        """
        Retorna True quando existem múltiplos mame.ini candidatos.
        """

        return self.root is not None and self.ini_folder is not None

    @property
    def available(self) -> list[Path]:
        """
        Retorna todos os arquivos encontrados.
        """

        result: list[Path] = []

        if self.root:
            result.append(self.root)

        if self.ini_folder:
            result.append(self.ini_folder)

        return result


class MameIniLocator:
    """
    Localiza arquivos mame.ini associados a uma instalação do MAME.
    """

    @staticmethod
    def find(mame_executable: Path) -> MameIniCandidates:
        """
        Procura mame.ini na raiz do executável e na pasta ./ini.
        """

        root = mame_executable.parent

        root_ini = root / "mame.ini"
        ini_folder = root / "ini" / "mame.ini"

        return MameIniCandidates(
            root=root_ini if root_ini.is_file() else None,
            ini_folder=ini_folder if ini_folder.is_file() else None,
        )