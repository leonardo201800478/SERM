"""Scanner de arquivos ZIP de ROM para o Arcade Studio.

O scanner lê um único arquivo de set, calcula a identidade do conteúdo de cada
entrada e devolve um inventário físico que pode ser comparado pelo SERM ao
catálogo MAME. Os arquivos originais nunca são modificados.
"""

from __future__ import annotations

import hashlib
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from .rom_reconstruction import PhysicalRom


class RomArchiveFormatError(ValueError):
    """Arquivo selecionado não é um ZIP de ROM suportado pelo scanner."""


@dataclass(frozen=True, slots=True)
class RomArchiveScanResult:
    """Resultado auditável do scan de um arquivo ZIP."""

    archive: str
    entries_scanned: int
    entries_skipped: int
    inventory: tuple[PhysicalRom, ...]


class RomArchiveScanner:
    """Lê um ZIP e gera identidade criptográfica para cada ROM."""

    def scan(self, archive: str | Path) -> RomArchiveScanResult:
        path = Path(archive)
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.casefold() != ".zip":
            raise RomArchiveFormatError(
                "O scan de arquivo do Arcade Studio suporta ZIP de ROMs nesta versão."
            )

        inventory: list[PhysicalRom] = []
        skipped = 0
        try:
            with zipfile.ZipFile(path, "r") as handle:
                for entry in handle.infolist():
                    if entry.is_dir():
                        skipped += 1
                        continue
                    data = handle.read(entry)
                    inventory.append(
                        PhysicalRom(
                            path=f"{path}!{entry.filename}",
                            size=len(data),
                            crc=f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
                            sha1=hashlib.sha1(data).hexdigest(),
                            md5=hashlib.md5(data).hexdigest(),
                        )
                    )
        except (zipfile.BadZipFile, OSError) as exc:
            raise RomArchiveFormatError(f"Não foi possível ler o ZIP: {exc}") from exc

        return RomArchiveScanResult(
            archive=str(path),
            entries_scanned=len(inventory),
            entries_skipped=skipped,
            inventory=tuple(inventory),
        )


__all__ = ["RomArchiveFormatError", "RomArchiveScanResult", "RomArchiveScanner"]
